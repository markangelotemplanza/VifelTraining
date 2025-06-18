from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class PalletKilosRecordModel(models.Model):
    _name = 'pallet_kilos_record_model.pallet_kilos_record_model'
    _description = 'Pallet Kilos Record Model'
    _order = 'id desc'  # Improve performance for searches that sort by ID
    
    # Basic identification fields
    report_no = fields.Char(string="Report No.", readonly=True)
    owner_id = fields.Many2one('res.partner', 'Owner', ondelete='set null', readonly=True, index=True)
    warehouse = fields.Many2one('stock.warehouse', 'Warehouse', ondelete='set null', readonly=True)
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
    # Storage operation fields
    pallets_received = fields.Float(store=True, string="Pallets Received", readonly=True)
    pallets_withdrawn = fields.Float(store=True, string="Pallets Withdrawn", readonly=True)
    kilos_received = fields.Float(store=True, string="Kilos Received", readonly=True)
    kilos_withdrawn = fields.Float(store=True, string="Kilos Withdrawn", readonly=True)
    
    # Computed fields with storage
    packaging_received = fields.Float(string="Packaging Received", readonly=True, 
                                    store=True, compute="_compute_operations")
    packaging_withdrawn = fields.Float(string="Packaging Withdrawn", readonly=True, 
                                     store=True, compute="_compute_operations")
    units_received = fields.Float(string="Units Received", readonly=True, 
                                store=True, compute="_compute_operations")
    units_withdrawn = fields.Float(string="Units Withdrawn", readonly=True, 
                                 store=True, compute="_compute_operations")

    # Balance fields with storage
    total_balance_in_units = fields.Float(store=True, string="Total Balance in Units", readonly=True)
    total_balance_in_packaging = fields.Float(store=True, string="Total Balance in Packaging", readonly=True)
    total_balance_in_kilos = fields.Float(store=True, string="Total Balance in Kilos (KG)", readonly=True)
    total_balance_in_pallets = fields.Float(store=True, string="Total Balance in Pallets", readonly=True)

    # Return fields with storage
    return_id = fields.Many2one('stock.picking', readonly=True, compute="_compute_returns", string="Return RR ID")
    return_heads = fields.Float(string="Total Return Units", readonly=True, 
                               compute="_compute_returns")
    return_packaging = fields.Float(string="Total Return Packaging", readonly=True, 
                                   compute="_compute_returns")
    return_pallets = fields.Float(string="Total Return Pallets", readonly=True, 
                                 compute="_compute_returns")
    return_kilos = fields.Float(string="Total Return Kilos", readonly=True, 
                               compute="_compute_returns")
    
    # Beginning balance fields with storage
    beginning_balance_in_pallets = fields.Float(string="Beginning Balance in Pallets", 
                                             readonly=True, store=True, compute="_compute_beginning_balance")
    beginning_balance_in_kilos = fields.Float(string="Beginning Balance in Kilos", 
                                           readonly=True, store=True, compute="_compute_beginning_balance")
    
    # Rate fields
    holding_rate = fields.Float(string='Holding Rate', related='owner_id.x_studio_holding_rate', store=True)
    handling_rate = fields.Float(string='Handling Rate', related='owner_id.x_studio_handling_rate', store=True)
    
    # Vehicle fields with storage - populated from effective document
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
    start_time = fields.Datetime(string="Start Time", readonly=True, store=True)
    end_time = fields.Datetime(string="End Time", readonly=True, store=True)
    # Maximum values
    max_pallets = fields.Many2one('x_inventory_static_var', 'Max Pallets', 
                                 default=lambda self: self._get_static_var('Max Pallets'))
    max_kg = fields.Many2one('x_inventory_static_var', 'Max Kilograms', 
                           default=lambda self: self._get_static_var('Max Kilograms'))


    # New computed fields for running balance
    overall_pallets = fields.Float(
        string='Overall Pallets',
        compute='_compute_overall_balance',
        # store=True
    )
    
    overall_kilos = fields.Float(
        string='Overall Kilos',
        compute='_compute_overall_balance',
        # store=True
    )

    def resync_all(self):
        # all_records = self.search([], order='start_time asc')
        for record in self:
            record._set_default_values_from_document(record.effective_document)
            record._compute_overall_balance()
            record._compute_beginning_balance()
            record._compute_operations()
            record._compute_returns()
            
    @api.depends('warehouse', 'pallets_received', 'pallets_withdrawn', 
                 'kilos_received', 'kilos_withdrawn')
    def _compute_overall_balance(self):
        for record in self:
            # Get all records for the same warehouse up to current record's date
            previous_records = self.search([
                ('record_reference.x_studio_is_a_blast_freezer', '=',  record.record_reference.x_studio_is_a_blast_freezer),
                ('warehouse', '=', record.warehouse.id),
                ('start_time', '<=', record.start_time),
                # ('id', '<=', record.id)
            ], order='start_time asc, id asc')
            
            # Calculate running totals
            total_pallets = sum(rec.pallets_received - rec.pallets_withdrawn for rec in previous_records)
            total_kilos = sum(rec.kilos_received - rec.kilos_withdrawn for rec in previous_records)
            
            record.overall_pallets = total_pallets
            record.overall_kilos = total_kilos
            
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
            # Use adjusted document if available, otherwise use original reference
            record.effective_document = record.readjustment_document or record.record_reference

    def _set_default_values_from_document(self, document):
        """Set truck type, plate and gate pass values from document"""
        if document:
            self.truck_type = document.truck_type
            self.trucks_plate = document.x_studio_trucks_plate_
            self.gate_pass = document.x_studio_gate_pass
            self.start_time = document.x_studio_start_time
            self.end_time = document.x_studio_end_time
        else:
            self._clear_default_values()
    
    def _clear_default_values(self):
        """Clear default values"""
        self.truck_type = False
        self.trucks_plate = False
        self.gate_pass = False

    @api.model
    def create(self, vals):
        """Override create to set default values on creation"""
        record = super(PalletKilosRecordModel, self).create(vals)
        
        # Set default values from the effective document
        effective_doc = record.readjustment_document or record.record_reference
        if effective_doc:
            record._set_default_values_from_document(effective_doc)
        
        return record

    def write(self, vals):
        """Override write to update default values when documents change"""
        result = super(PalletKilosRecordModel, self).write(vals)
        
        # If either document was updated, refresh default values
        if 'record_reference' in vals or 'readjustment_document' in vals:
            for record in self:
                effective_doc = record.readjustment_document or record.record_reference
                if effective_doc:
                    record._set_default_values_from_document(effective_doc)
                else:
                    record._clear_default_values()
        
        return result
    
    @api.depends('effective_document')
    def _compute_operations(self):
        """Compute packaging and units operations using effective document"""
        for record in self:
            units_received = 0
            units_withdrawn = 0
            packaging_received = 0
            packaging_withdrawn = 0
            kilos_received = 0
            kilos_withdrawn = 0
            pallets = set()
            pallet_count = 0
            
            if record.effective_document:
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
                                package_id_record = self.env['stock.quant.package'].browse(move_line.package_id.id)
                                # total_quantity = sum(package_id_record.quant_ids.mapped('quantity'))
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
                    record.units_received = units_received
                    record.packaging_received = packaging_received
                    record.kilos_received = kilos_received
                    record.pallets_received = pallet_count
                    record.units_withdrawn = 0
                    record.packaging_withdrawn = 0
                    record.kilos_withdrawn = 0
                    record.pallets_withdrawn = 0
                
                elif picking_code == 'outgoing':
                    record.units_withdrawn = units_withdrawn
                    record.packaging_withdrawn = packaging_withdrawn
                    record.kilos_withdrawn = kilos_withdrawn
                    record.pallets_withdrawn = pallet_count
                    record.units_received = 0
                    record.packaging_received = 0
                    record.kilos_received = 0
                    record.pallets_received = 0
                
                else:
                    # Neutral state for other types
                    record.units_received = 0
                    record.packaging_received = 0
                    record.units_withdrawn = 0
                    record.packaging_withdrawn = 0
                    record.kilos_received = 0
                    record.kilos_withdrawn = 0
                    record.pallets_received = 0
                    record.pallets_withdrawn = 0
            else:
                # Clear all values if no effective document
                record.units_received = 0
                record.packaging_received = 0
                record.units_withdrawn = 0
                record.packaging_withdrawn = 0
                record.kilos_received = 0
                record.kilos_withdrawn = 0
                record.pallets_received = 0
                record.pallets_withdrawn = 0
    
    @api.depends('effective_document')
    def _compute_returns(self):
        """Compute return values using effective document"""
        for record in self:
            return_heads = 0
            return_packaging = 0
            return_pallets = 0
            return_kilos = 0
            pallets = set()
            
            # Default value to avoid compute error
            record.return_id = False
    
            if record.effective_document:
                for returns in record.effective_document.return_ids:
                    if returns.state == 'done' and returns.return_reason == 'Partial Withdraw' and not returns.x_studio_voided:
                        record.return_id = returns.id
                        for line_ids in returns.move_line_ids:
                            return_heads += line_ids.x_studio_total_units
                            return_packaging += line_ids.x_studio_2nd_uom
                            return_kilos += line_ids.quantity
                            if line_ids.result_package_id and line_ids.result_package_id.id not in pallets:
                                return_pallets += 1
                                pallets.add(line_ids.result_package_id.id)
                        break  # break after first matching return
    
            record.return_heads = return_heads
            record.return_packaging = return_packaging
            record.return_pallets = return_pallets
            record.return_kilos = return_kilos
    
    @api.depends('owner_id', 'effective_document.picking_type_id.name')
    def _compute_beginning_balance(self):
        """Compute beginning balance values using effective document"""
        for record in self:
            # Initialize values
            record.beginning_balance_in_pallets = 0.0
            record.beginning_balance_in_kilos = 0.0
            
            if not record.owner_id or not record.effective_document:
                continue
            
            # Determine record type category
            picking_type_name = record.effective_document.picking_type_id.name
            category = None
            
            if picking_type_name in ['Receipts', 'Delivery Orders']:
                category = ['Receipts', 'Delivery Orders']
            elif picking_type_name in ['Blast Freeze - IN', 'Blast Freeze - OUT']:
                category = ['Blast Freeze - IN', 'Blast Freeze - OUT']
            
            if category:
                # Search for previous records in this category
                prev = self.search([
                    ('owner_id', '=', record.owner_id.id),
                    ('start_time', '<', record.start_time),
                    # ('effective_document.picking_type_id.name', 'in', category)
                ], order='start_time desc', limit=1)
                
                # Ensure operations are computed
                record._compute_operations()
                # begin - begin + rr - wr
                # Set beginning balances from previous record
                if prev:
                    record.beginning_balance_in_pallets = prev.total_balance_in_pallets
                    record.beginning_balance_in_kilos = prev.total_balance_in_kilos

                    if record.effective_document.picking_type_id.code == 'outgoing':
                        record.total_balance_in_packaging = prev.total_balance_in_packaging - record.packaging_withdrawn
                        record.total_balance_in_units = prev.total_balance_in_units - record.units_withdrawn
                        record.total_balance_in_kilos = prev.total_balance_in_kilos - record.kilos_withdrawn
                        record.total_balance_in_pallets = prev.total_balance_in_pallets - record.pallets_withdrawn
                    elif record.effective_document.picking_type_id.code == 'incoming':
                        record.total_balance_in_packaging = prev.total_balance_in_packaging + record.packaging_received
                        record.total_balance_in_units = prev.total_balance_in_units + record.units_received
                        record.total_balance_in_kilos = prev.total_balance_in_kilos + record.kilos_received
                        record.total_balance_in_pallets = prev.total_balance_in_pallets + record.pallets_received
                else:
                    # First record - set beginning balance to 0 and total balance to received amounts
                    record.beginning_balance_in_pallets = 0
                    record.beginning_balance_in_kilos = 0
                    record.total_balance_in_packaging = record.packaging_received
                    record.total_balance_in_units = record.units_received
                    record.total_balance_in_kilos = record.kilos_received
                    record.total_balance_in_pallets = record.pallets_received

