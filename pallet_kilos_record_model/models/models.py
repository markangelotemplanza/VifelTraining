from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class PalletKilosRecordModel(models.Model):
    _name = 'pallet_kilos_record_model.pallet_kilos_record_model'
    _description = 'Pallet Kilos Record Model'
    _order = 'start_time asc, id asc'  # Critical for running balance
    
    # Basic identification fields
    report_no = fields.Char(string="Report No.", readonly=True)
    owner_id = fields.Many2one('res.partner', 'Owner', ondelete='set null', readonly=True, index=True)
    warehouse = fields.Many2one('stock.warehouse', 'Warehouse', ondelete='set null', readonly=True, index=True)
    record_reference = fields.Many2one('stock.picking', 'Record Reference', store=True, ondelete='set null', 
                                      readonly=True, index=True)

    active = fields.Boolean(string="active", default=True)
    # Adjusted document - this replaces the original reference for computations
    readjustment_document = fields.Many2one('stock.picking', string="Adjusted Document Reference", 
                                          ondelete='set null', readonly=True, index=True,
                                          help="When set, this document replaces the original reference for all calculations")
    
    # Effective document - computed field that returns either adjusted or original reference
    effective_document = fields.Many2one('stock.picking', string="Effective Document", 
                                       compute='_compute_effective_document', store=True,
                                       help="The document used for all calculations (adjusted if available, otherwise original)")
    operation_type_id = fields.Many2one(string="Operation Type", related="effective_document.picking_type_id", store=True)
    
    # Storage operation fields - these will be populated directly, not computed
    pallets_received = fields.Float(store=True, string="Pallets Received", readonly=True)
    pallets_withdrawn = fields.Float(store=True, string="Pallets Withdrawn", readonly=True)
    kilos_received = fields.Float(store=True, string="Kilos Received", readonly=True)
    kilos_withdrawn = fields.Float(store=True, string="Kilos Withdrawn", readonly=True)
    
    # Operation fields - stored, not computed
    packaging_received = fields.Float(string="Packaging Received", readonly=True, store=True)
    packaging_withdrawn = fields.Float(string="Packaging Withdrawn", readonly=True, store=True)
    units_received = fields.Float(string="Units Received", readonly=True, store=True)
    units_withdrawn = fields.Float(string="Units Withdrawn", readonly=True, store=True)

    # Balance fields - stored, calculated via method calls
    total_balance_in_units = fields.Float(store=True, string="Total Balance in Units", readonly=True)
    total_balance_in_packaging = fields.Float(store=True, string="Total Balance in Packaging", readonly=True)
    total_balance_in_kilos = fields.Float(store=True, string="Total Balance in Kilos (KG)", readonly=True)
    total_balance_in_pallets = fields.Float(store=True, string="Total Balance in Pallets", readonly=True)

    # Return fields - stored, not computed
    return_id = fields.Many2one('stock.picking', readonly=True, string="Return RR ID")
    return_heads = fields.Float(string="Total Return Units", readonly=True)
    return_packaging = fields.Float(string="Total Return Packaging", readonly=True)
    return_pallets = fields.Float(string="Total Return Pallets", readonly=True)
    return_kilos = fields.Float(string="Total Return Kilos", readonly=True)
    
    # Beginning balance fields - stored, calculated via method calls
    beginning_balance_in_pallets = fields.Float(string="Beginning Balance in Pallets", readonly=True, store=True)
    beginning_balance_in_kilos = fields.Float(string="Beginning Balance in Kilos", readonly=True, store=True)
    
    # Rate fields
    holding_rate = fields.Float(string='Holding Rate', related='owner_id.x_studio_holding_rate', store=True)
    handling_rate = fields.Float(string='Handling Rate', related='owner_id.x_studio_handling_rate', store=True)
    
    # Vehicle fields - stored
    truck_type = fields.Selection(
        selection=[
            ('4wheeler', '4 Wheeler'),
            ('6wheeler', '6 Wheeler'),
            ('10wheeler', '10 Wheeler'),
            ('20ft_container', '20ft Container'),
            ('40ft_container', '40ft Container'),
            ('N/A', 'N/A')
        ],
        string="Truck Type", readonly=True, store=True
    )
    trucks_plate = fields.Char(string="Truck's Plate #", readonly=True, store=True)
    gate_pass = fields.Char(string="Gate Pass #", readonly=True, store=True)
    start_time = fields.Datetime(string="Start Time", readonly=True, store=True, index=True)  # INDEX IS CRITICAL
    end_time = fields.Datetime(string="End Time", readonly=True, store=True)
    
    # Maximum values
    max_pallets = fields.Many2one('x_inventory_static_var', 'Max Pallets', 
                                 default=lambda self: self._get_static_var('Max Pallets'))
    max_kg = fields.Many2one('x_inventory_static_var', 'Max Kilograms', 
                           default=lambda self: self._get_static_var('Max Kilograms'))

    # Running balance fields - stored, not computed
    overall_pallets = fields.Float(string='Overall Pallets', store=True)
    overall_kilos = fields.Float(string='Overall Kilos', store=True)
    
    # Add blast freezer flag for efficient filtering
    is_blast_freezer = fields.Boolean(string="Is Blast Freezer", store=True, index=True)

    @api.model
    def _get_static_var(self, var_name):
        """Get static variable from inventory_static_var model by name"""
        return self.env['x_inventory_static_var'].search([
            ('x_studio_use_case', '=', 'XLSX Variables'),
            ('x_name', 'ilike', var_name)
        ], limit=1)

    @api.depends('record_reference', 'readjustment_document')
    def _compute_effective_document(self):
        """Compute the effective document to use for calculations"""
        for record in self:
            record.effective_document = record.readjustment_document or record.record_reference

    def _populate_operations_data(self):
        """Populate operation data from effective document - called explicitly, not computed"""
        for record in self:
            if not record.effective_document:
                continue
                
            units_received = 0
            units_withdrawn = 0
            packaging_received = 0
            packaging_withdrawn = 0
            kilos_received = 0
            kilos_withdrawn = 0
            pallets = set()
            pallet_count = 0
            
            # Get move lines data from effective document
            for line in record.effective_document.move_ids_without_package:
                units_received += line.x_studio_min_actual_demand
                packaging_received += line.x_studio_actual_packaging_demand
                units_withdrawn += line.x_studio_min_actual_demand
                packaging_withdrawn += line.x_studio_actual_packaging_demand
                kilos_received += line.quantity
                kilos_withdrawn += line.quantity

            # Count unique pallets
            if record.effective_document.picking_type_id.name in ['Delivery Orders']:
                for move_line in record.effective_document.move_line_ids:
                    if move_line.picking_id.x_studio_is_a_blast_freezer:
                        if move_line.bf_pallet_char not in pallets:
                            pallet_count += 1
                            pallets.add(move_line.bf_pallet_char)
                    else:
                        if move_line.package_id and move_line.package_id.id not in pallets:               
                            if move_line.reserved_quantity_on_validation == 0:
                                pallet_count += 1
                                pallets.add(move_line.package_id.id)
            else:
                for move_line in record.effective_document.move_line_ids:
                    if move_line.picking_id.x_studio_is_a_blast_freezer:
                        if move_line.bf_pallet_char not in pallets:
                            pallet_count += 1
                            pallets.add(move_line.bf_pallet_char)
                    else:
                        if move_line.result_package_id and move_line.result_package_id.id not in pallets:
                            pallet_count += 1
                            pallets.add(move_line.result_package_id.id)
                    
            # Set values based on picking type
            picking_code = record.effective_document.picking_type_id.code
            
            if picking_code == 'incoming':
                record.write({
                    'units_received': units_received,
                    'packaging_received': packaging_received,
                    'kilos_received': kilos_received,
                    'pallets_received': pallet_count,
                    'units_withdrawn': 0,
                    'packaging_withdrawn': 0,
                    'kilos_withdrawn': 0,
                    'pallets_withdrawn': 0,
                    'is_blast_freezer': record.effective_document.x_studio_is_a_blast_freezer or False
                })
            elif picking_code == 'outgoing':
                record.write({
                    'units_withdrawn': units_withdrawn,
                    'packaging_withdrawn': packaging_withdrawn,
                    'kilos_withdrawn': kilos_withdrawn,
                    'pallets_withdrawn': pallet_count,
                    'units_received': 0,
                    'packaging_received': 0,
                    'kilos_received': 0,
                    'pallets_received': 0,
                    'is_blast_freezer': record.effective_document.x_studio_is_a_blast_freezer or False
                })

    def _populate_returns_data(self):
        """Populate return data from effective document - called explicitly"""
        for record in self:
            if not record.effective_document:
                continue
                
            return_heads = 0
            return_packaging = 0
            return_pallets = 0
            return_kilos = 0
            return_id = False
            pallets = set()

            for returns in record.effective_document.return_ids:
                if returns.state == 'done' and returns.return_reason == 'Partial Withdraw' and not returns.x_studio_voided:
                    return_id = returns.id
                    for line_ids in returns.move_line_ids:
                        return_heads += line_ids.x_studio_total_units
                        return_packaging += line_ids.x_studio_2nd_uom
                        return_kilos += line_ids.quantity
                        if line_ids.result_package_id and line_ids.result_package_id.id not in pallets:
                            return_pallets += 1
                            pallets.add(line_ids.result_package_id.id)
                    break

            record.write({
                'return_id': return_id,
                'return_heads': return_heads,
                'return_packaging': return_packaging,
                'return_pallets': return_pallets,
                'return_kilos': return_kilos,
            })

    def _populate_vehicle_data(self):
        """Populate vehicle data from effective document"""
        for record in self:
            if record.effective_document:
                record.write({
                    'truck_type': record.effective_document.truck_type,
                    'trucks_plate': record.effective_document.x_studio_trucks_plate_,
                    'gate_pass': record.effective_document.x_studio_gate_pass,
                    'start_time': record.effective_document.x_studio_start_time,
                    'end_time': record.effective_document.x_studio_end_time,
                })

    def _recalculate_running_balances(self, warehouse_id, blast_freezer_flag, from_datetime=None):
        """
        Efficiently recalculate running balances for all records in a warehouse after a given datetime
        """
        domain = [
            ('warehouse', '=', warehouse_id),
            ('is_blast_freezer', '=', blast_freezer_flag),
        ]
        
        if from_datetime:
            domain.append(('start_time', '>=', from_datetime))
        
        # Get all affected records in chronological order
        records_to_update = self.search(domain, order='start_time asc, id asc')
        
        if not records_to_update:
            return
        
        # Get the previous balance (record just before the from_datetime)
        if from_datetime:
            prev_record = self.search([
                ('warehouse', '=', warehouse_id),
                ('is_blast_freezer', '=', blast_freezer_flag),
                ('start_time', '<', from_datetime)
            ], order='start_time desc, id desc', limit=1)
            
            if prev_record:
                running_pallets = prev_record.overall_pallets
                running_kilos = prev_record.overall_kilos
                prev_total_pallets = prev_record.total_balance_in_pallets
                prev_total_kilos = prev_record.total_balance_in_kilos
                prev_total_units = prev_record.total_balance_in_units
                prev_total_packaging = prev_record.total_balance_in_packaging
            else:
                running_pallets = running_kilos = 0
                prev_total_pallets = prev_total_kilos = prev_total_units = prev_total_packaging = 0
        else:
            running_pallets = running_kilos = 0
            prev_total_pallets = prev_total_kilos = prev_total_units = prev_total_packaging = 0

        # Batch update all records
        updates = []
        for record in records_to_update:
            # Calculate running totals
            running_pallets += (record.pallets_received - record.pallets_withdrawn)
            running_kilos += (record.kilos_received - record.kilos_withdrawn)
            
            # Calculate balance totals
            if record.effective_document and record.effective_document.picking_type_id.code == 'outgoing':
                current_total_packaging = prev_total_packaging - record.packaging_withdrawn
                current_total_units = prev_total_units - record.units_withdrawn
                current_total_kilos = prev_total_kilos - record.kilos_withdrawn
                current_total_pallets = prev_total_pallets - record.pallets_withdrawn
            elif record.effective_document and record.effective_document.picking_type_id.code == 'incoming':
                current_total_packaging = prev_total_packaging + record.packaging_received
                current_total_units = prev_total_units + record.units_received
                current_total_kilos = prev_total_kilos + record.kilos_received
                current_total_pallets = prev_total_pallets + record.pallets_received
            else:
                current_total_packaging = prev_total_packaging
                current_total_units = prev_total_units
                current_total_kilos = prev_total_kilos
                current_total_pallets = prev_total_pallets

            updates.append({
                'id': record.id,
                'overall_pallets': running_pallets,
                'overall_kilos': running_kilos,
                'beginning_balance_in_pallets': prev_total_pallets,
                'beginning_balance_in_kilos': prev_total_kilos,
                'total_balance_in_units': current_total_units,
                'total_balance_in_packaging': current_total_packaging,
                'total_balance_in_kilos': current_total_kilos,
                'total_balance_in_pallets': current_total_pallets,
            })
            
            # Update previous values for next iteration
            prev_total_pallets = current_total_pallets
            prev_total_kilos = current_total_kilos
            prev_total_units = current_total_units
            prev_total_packaging = current_total_packaging

        # Batch write all updates
        for update in updates:
            record_id = update.pop('id')
            self.browse(record_id).write(update)

    @api.model
    def create(self, vals):
        """Override create to handle backdated insertions"""
        record = super(PalletKilosRecordModel, self).create(vals)
        
        # Populate all data first
        record._populate_vehicle_data()
        record._populate_operations_data()
        record._populate_returns_data()
        
        # Check if this is a backdated insertion
        if record.start_time and record.warehouse:
            later_records = self.search([
                ('warehouse', '=', record.warehouse.id),
                ('is_blast_freezer', '=', record.is_blast_freezer),
                ('start_time', '>', record.start_time),
                ('id', '!=', record.id)
            ], limit=1)
            
            if later_records:
                # This is a backdated insertion - recalculate from this point forward
                _logger.info(f"Backdated insertion detected for warehouse {record.warehouse.name} at {record.start_time}")
                record._recalculate_running_balances(
                    record.warehouse.id, 
                    record.is_blast_freezer, 
                    record.start_time
                )
            else:
                # This is the latest record - just calculate its balance
                record._recalculate_running_balances(
                    record.warehouse.id, 
                    record.is_blast_freezer, 
                    record.start_time
                )
        
        return record

    def write(self, vals):
        """Override write to handle document changes and start_time changes"""
        # Store original values for comparison
        original_data = {}
        for record in self:
            original_data[record.id] = {
                'start_time': record.start_time,
                'warehouse_id': record.warehouse.id if record.warehouse else None,
                'is_blast_freezer': record.is_blast_freezer,
            }
        
        result = super(PalletKilosRecordModel, self).write(vals)
        
        # Handle document changes
        if 'record_reference' in vals or 'readjustment_document' in vals:
            for record in self:
                record._populate_vehicle_data()
                record._populate_operations_data()
                record._populate_returns_data()

        # Handle start_time changes (potential backdating)
        if 'start_time' in vals:
            for record in self:
                old_data = original_data[record.id]
                if (record.start_time != old_data['start_time'] and 
                    record.warehouse and record.start_time):
                    
                    # Recalculate from the earlier of old or new start_time
                    earliest_time = min(record.start_time, old_data['start_time']) if old_data['start_time'] else record.start_time
                    record._recalculate_running_balances(
                        record.warehouse.id,
                        record.is_blast_freezer,
                        earliest_time
                    )
        
        return result

    def unlink(self):
        """Override unlink to recalculate balances after deletion"""
        records_to_recalc = []
        for record in self:
            if record.warehouse and record.start_time:
                records_to_recalc.append({
                    'warehouse_id': record.warehouse.id,
                    'is_blast_freezer': record.is_blast_freezer,
                    'start_time': record.start_time,
                })
        
        result = super(PalletKilosRecordModel, self).unlink()
        
        # Recalculate balances for affected warehouses
        for data in records_to_recalc:
            self._recalculate_running_balances(
                data['warehouse_id'],
                data['is_blast_freezer'],
                data['start_time']
            )
        
        return result

    def manual_recalculate_all(self):
        """Manual method to recalculate all running balances - for maintenance"""
        warehouses = self.search([]).mapped('warehouse')
        for warehouse in warehouses:
            for blast_freezer in [True, False]:
                self._recalculate_running_balances(warehouse.id, blast_freezer)

    def resync_all(self):
        """Resync current record"""
        for record in self:
            record._populate_vehicle_data()
            record._populate_operations_data()
            record._populate_returns_data()
            record._recalculate_running_balances(
                record.warehouse.id,
                record.is_blast_freezer,
                record.start_time
            )

    def resync_all_2(self):
        """Resync all records in chronological order"""
        all_records = self.search([], order='start_time asc')
        warehouses_processed = set()
        
        for record in all_records:
            record._populate_vehicle_data()
            record._populate_operations_data()
            record._populate_returns_data()
            
            # Only recalculate once per warehouse-blast_freezer combination
            key = (record.warehouse.id, record.is_blast_freezer)
            if key not in warehouses_processed:
                record._recalculate_running_balances(record.warehouse.id, record.is_blast_freezer)
                warehouses_processed.add(key)