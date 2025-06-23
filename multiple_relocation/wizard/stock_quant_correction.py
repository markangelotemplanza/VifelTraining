# models/stock_quant_correction_wizard.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class StockQuantCorrectionWizard(models.TransientModel):
    _name = 'stock.quant.correction.wizard'
    _description = 'Stock Quant Correction Wizard'

    line_ids = fields.One2many('stock.quant.correction.line', 'wizard_id', string='Quant Corrections')
    reason_for_adjustment = fields.Char(string="Reason for Adjustment", required=True)

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Get selected quants from context
        quant_ids = self.env.context.get('active_ids', [])
        if not quant_ids:
            raise UserError(_("Please select at least one stock quant to correct."))
            
        # Validate selected quants
        quants = self.env['stock.quant'].browse(quant_ids)
        
        # Check for reserved quantities
        reserved_quants = quants.filtered(lambda q: q.reserved_quantity > 0)
        if reserved_quants:
            raise UserError(_("Cannot modify quants with reserved quantities. "
                            "Please unreserve the following quants first:\n%s") % 
                          '\n'.join(reserved_quants.mapped('product_id.name')))
        
        # Create wizard lines
        line_vals = []
        for quant in quants:
            line_vals.append({
                'quant_id': quant.id,
                'package_id': quant.package_id.id,
                'x_studio_pallet_series_id': quant.x_studio_pallet_series_id,
                'product_id': quant.product_id.id,
                'x_studio_production_date': quant.x_studio_production_date,
                'x_studio_expiration_date': quant.x_studio_expiration_date,
                'x_studio_loading_dock_no': quant.x_studio_loading_dock_no,
                'x_studio_source': quant.x_studio_source,
                'x_studio_gate_pass': quant.x_studio_gate_pass,
                'x_studio_truck_time': quant.x_studio_truck_time,
                'x_studio_start_time': quant.x_studio_start_time,
                'x_studio_end_time': quant.x_studio_end_time,
                'x_studio_truck_number': quant.x_studio_truck_number,
                'x_studio_2nd_uom': quant.x_studio_2nd_uom,
                'x_studio_quantity_uom': quant.x_studio_quantity_uom.id,
                'x_studio_total_units': quant.x_studio_total_units,
                'x_studio_min_quantity_uom': quant.x_studio_min_quantity_uom.id,
                'quantity': quant.quantity,
                'lot_id': quant.lot_id.id,
                'owner_id': quant.owner_id.id,
            })
        
        res['line_ids'] = [(0, 0, vals) for vals in line_vals]
        return res

    def action_confirm_corrections(self):
        """Process all corrections and create stock moves for history tracking"""
        adjustment_form_series = self.env['ir.sequence'].search([('code', '=', 'adjustment.form.series')], limit=1)
        batch_number = adjustment_form_series.next_by_id()
        for line in self.line_ids:
            changes = line._get_changes()
            if changes:
                # Store original quant state before changes
                original_state = line._capture_original_state()
                
                # Update the quant first
                line._apply_changes(changes)
                
                # Create stock move for history tracking AFTER updating the quant
                # This ensures the move references the updated quant state
                self._create_correction_move(line, changes, original_state, batch_number, line.quant_id.x_studio_record_reference)
        
        return {'type': 'ir.actions.act_window_close'}

    def _create_correction_move(self, line, changes, original_state, batch_number, picking_id):
        """Create stock move to track the correction in history"""
        
        quant = line.quant_id
        
        # Get inventory adjustment locations
        inventory_location = self.env.ref('stock.location_inventory', raise_if_not_found=False)
        if not inventory_location:
            # Fallback: find or create inventory location
            inventory_location = self.env['stock.location'].search([
                ('usage', '=', 'inventory')
            ], limit=1)
            if not inventory_location:
                raise UserError(_("Inventory location not found. Please configure inventory adjustments."))
        
        # Create the correction description
        correction_description = self._format_changes_description(changes)
        
        # Create stock move for correction tracking
        move_vals = {
            'name': f'Correction: {original_state["product_name"]} - {correction_description}',
            'product_id': quant.product_id.id,  # Use current product after correction
            'product_uom': quant.product_id.uom_id.id,
            'product_uom_qty': quant.quantity,
            'location_id': inventory_location.id,
            'location_dest_id': quant.location_id.id,
            'origin': 'Stock Quant Correction',
            'date': fields.Datetime.now(),

        }
        
        move = self.env['stock.move'].create(move_vals)
        
        # Create stock move line with correction details using ORIGINAL state info
        move_line_vals = {
            'move_id': move.id,
            'product_id': quant.product_id.id,  # Current product
            'product_uom_id': quant.product_id.uom_id.id,
            'quantity': quant.quantity,
            'location_id': inventory_location.id,
            'location_dest_id': quant.location_id.id,
            'lot_id': quant.lot_id.id if quant.lot_id else False,  # Current lot
            'package_id': quant.package_id.id if quant.package_id else False,
            'result_package_id': quant.package_id.id if quant.package_id else False,
            'reference': self._format_changes_reference(changes, original_state),
            'x_studio_pallet_series_id': quant.x_studio_pallet_series_id,
            'is_quant_detail_adjusted': True,
            'owner_id': quant.owner_id.id,
            'state': 'done',
            'adjustment_batch_number': batch_number,
            'adjustment_reference_id': quant.x_studio_record_reference.id if quant.x_studio_record_reference else False
        }
        
        # Add custom fields to move line - use current values after correction
        for field_name in changes.keys():
            if hasattr(self.env['stock.move.line'], field_name):
                current_value = getattr(quant, field_name, False)
                if field_name in ['x_studio_production_date', 'x_studio_expiration_date']:
                    move_line_vals[field_name] = current_value
                elif field_name.startswith('x_studio_'):
                    move_line_vals[field_name] = current_value
        
        move_line = self.env['stock.move.line'].create(move_line_vals)
        
        # Set move as done to make it appear in history
        move.write({'state': 'done'})
        
        return move

    def _format_changes_description(self, changes):
        """Format changes for move name"""
        if len(changes) == 1:
            field, (old_val, new_val) = list(changes.items())[0]
            return f"{field} updated"
        else:
            return f"{len(changes)} fields updated"


    def _format_changes_reference(self, changes, original_state):
        """Format changes for reference field, including timestamp and user"""
        change_list = []
        for field, (old_val, new_val) in changes.items():
            # For product changes, use original product name if available
            if field == 'product_id':
                old_display = original_state.get('product_name', 'Unknown')
                new_display = original_state.get('new_product_name', str(new_val))
            else:
                old_display = self._format_value_for_display(old_val)
                new_display = self._format_value_for_display(new_val)
    
            # Clean and title-case field name
            display_field = field.replace('x_studio_', '').replace('_', ' ').title()
    
            # Append formatted field change, wrapped in []
            change_list.append(f"[{display_field}: {old_display} → {new_display}]")
    
        # Timestamp and user info
        timestamp = datetime.now().strftime('%m/%d/%y %H:%M:%S')
        user = self.env.user.name
        return f"CORRECTION ({timestamp} by {user}): " + " ".join(change_list)

    
    def _format_value_for_display(self, value):
        """Format a value for display in reference"""
        if value is False or value is None:
            return "Empty"
        elif isinstance(value, (int, float)) and str(value).endswith('.0'):
            return str(int(value))
        else:
            return str(value)


class StockQuantCorrectionLine(models.TransientModel):
    _name = 'stock.quant.correction.line'
    _description = 'Stock Quant Correction Line'

    wizard_id = fields.Many2one('stock.quant.correction.wizard', required=True, ondelete='cascade')
    quant_id = fields.Many2one('stock.quant', string='Original Quant', required=True)
    
    # All editable fields from stock.quant
    package_id = fields.Many2one('stock.quant.package', string='Package')
    x_studio_pallet_series_id = fields.Char(string='Pallet Series')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    x_studio_production_date = fields.Date(string='Production Date')
    x_studio_expiration_date = fields.Date(string='Expiration Date')
    x_studio_loading_dock_no = fields.Char(string='Loading Dock No')
    x_studio_source = fields.Char(string='Source')
    x_studio_gate_pass = fields.Char(string='Gate Pass')
    x_studio_truck_time = fields.Datetime(string='Truck Time')
    x_studio_start_time = fields.Datetime(string='Start Time')
    x_studio_end_time = fields.Datetime(string='End Time')
    x_studio_truck_number = fields.Char(string='Truck Number')
    x_studio_2nd_uom = fields.Float(string='2nd UOM')
    x_studio_quantity_uom = fields.Many2one('uom.uom', string='Quantity UOM')
    x_studio_total_units = fields.Float(string='Total Units')
    x_studio_min_quantity_uom = fields.Many2one('uom.uom', string='Min Quantity UOM')
    owner_id = fields.Many2one('res.partner', string="Owner")
    quantity = fields.Float(string='Quantity')
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial', readonly=True)

    
    @api.onchange('select_all')
    def _onchange_select_all(self):
        for line in self.line_ids:
            line.selected = self.select_all
    def _capture_original_state(self):
        """Capture the original state of the quant before changes"""
        self.ensure_one()
        quant = self.quant_id
        
        original_state = {
            'product_name': quant.product_id.name,
            'product_id': quant.product_id.id,
            'lot_id': quant.lot_id.id if quant.lot_id else False,
            'package_id': quant.package_id.id if quant.package_id else False,
        }
        
        # Add new product name if product is being changed
        if hasattr(self, 'product_id') and self.product_id != quant.product_id:
            original_state['new_product_name'] = self.product_id.name
        
        return original_state

    def _check_dates(self):
        for line in self:
            if (line.x_studio_production_date and line.x_studio_expiration_date and 
                line.x_studio_production_date > line.x_studio_expiration_date):
                raise ValidationError(_("Production date cannot be later than expiration date."))

    def _get_changes(self):
        """Compare current values with original quant and return changes"""
        self.ensure_one()
        quant = self.quant_id
        
        changes = {}
        field_mapping = {
            'package_id': ('package_id', lambda x: x.id if x else False),
            'x_studio_pallet_series_id': ('x_studio_pallet_series_id', str),
            'product_id': ('product_id', lambda x: x.id),
            'x_studio_production_date': ('x_studio_production_date', str),
            'x_studio_expiration_date': ('x_studio_expiration_date', str),
            'x_studio_loading_dock_no': ('x_studio_loading_dock_no', str),
            'x_studio_source': ('x_studio_source', str),
            'x_studio_gate_pass': ('x_studio_gate_pass', str),
            'x_studio_truck_time': ('x_studio_truck_time', str),
            'x_studio_start_time': ('x_studio_start_time', str),
            'x_studio_end_time': ('x_studio_end_time', str),
            'x_studio_truck_number': ('x_studio_truck_number', str),
            'x_studio_2nd_uom': ('x_studio_2nd_uom', float),
            'x_studio_quantity_uom': ('x_studio_quantity_uom', lambda x: x.id if x else False),
            'x_studio_total_units': ('x_studio_total_units', float),
            'x_studio_min_quantity_uom': ('x_studio_min_quantity_uom', lambda x: x.id if x else False),
            'owner_id': ('owner_id', lambda x: x.id if x else False),
            'quantity': ('quantity', float),
        }
        
        for wizard_field, (quant_field, converter) in field_mapping.items():
            old_value = getattr(quant, quant_field)
            new_value = getattr(self, wizard_field)
            
            # Convert for comparison
            try:
                old_converted = converter(old_value) if old_value not in [False, None] else old_value
                new_converted = converter(new_value) if new_value not in [False, None] else new_value
            except (ValueError, TypeError):
                old_converted = old_value
                new_converted = new_value
            
            if old_converted != new_converted:
                changes[quant_field] = (old_converted, new_converted)
        
        return changes

    def _apply_changes(self, changes):
        """Apply changes to the original quant"""
        self.ensure_one()
        quant = self.quant_id
        
        # Prepare values for update
        update_vals = {}
        for field, (old_val, new_val) in changes.items():
            update_vals[field] = new_val
        
        # Special handling for product change - FORCE the same lot to accept new product
        if 'product_id' in changes and quant.lot_id:
            try:
                # CRITICAL: We must keep the same exact lot_id and force it to accept the new product
                # This bypasses Odoo's product compatibility validation
                
                # Find existing stock move lines related to this lot
                existing_move_lines = self.env['stock.move.line'].search([
                    ('lot_id', '=', quant.lot_id.id)
                ])
                
                # Find related stock moves
                existing_moves = existing_move_lines.mapped('move_id')
                
                # Store original states of moves that need to be put back to done
                moves_to_restore = existing_moves.filtered(lambda m: m.state == 'done')
                
                # Set moves to draft to allow product changes
                if existing_moves:
                    existing_moves.sudo().write({'state': 'draft'})
                
                # Update move lines product first
                if existing_move_lines:
                    existing_move_lines.sudo().write({'product_id': update_vals['product_id']})
                
                # Update moves product
                if existing_moves:
                    existing_moves.sudo().write({'product_id': update_vals['product_id']})
                
                # FORCE update the lot's product - bypass compatibility check using sudo() and _write
                # This directly writes to the database without triggering Odoo's validation
                quant.lot_id.sudo()._write({'product_id': update_vals['product_id']})
                
                # Alternative method if _write doesn't work - use SQL direct update
                if hasattr(quant.lot_id, '_cr'):
                    try:
                        quant.lot_id._cr.execute(
                            "UPDATE stock_lot SET product_id = %s WHERE id = %s",
                            (update_vals['product_id'], quant.lot_id.id)
                        )
                        quant.lot_id._cr.commit()
                        # Invalidate cache to refresh the record
                        quant.lot_id.invalidate_recordset(['product_id'])
                    except Exception:
                        pass  # Fallback if SQL update fails
                
                # Restore done state for moves that were originally done
                if moves_to_restore:
                    moves_to_restore.sudo().write({'state': 'done'})
                
            except Exception as e:
                raise UserError(_("Failed to force update lot product (keeping same lot_id): %s") % str(e))
        
        # Update the quant
        if update_vals:
            quant.write(update_vals)