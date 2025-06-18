# from odoo import models, fields, api
# from odoo.exceptions import ValidationError, UserError
# from datetime import datetime, timedelta
# import logging
# _logger = logging.getLogger(__name__)

# class PalletKilosRecordModel(models.Model):
#     _name = 'pallet_kilos_record_model.pallet_kilos_record_model'
#     _description = 'Pallet Kilos Record Model'
#     _order = 'id desc'  # Improve performance for searches that sort by ID
    
#     # Basic identification fields
#     report_no = fields.Char(string="Report No.", readonly=True)
#     owner_id = fields.Many2one('res.partner', 'Owner', ondelete='set null', readonly=True, index=True)
#     warehouse = fields.Many2one('stock.warehouse', 'Warehouse', ondelete='set null', readonly=True)
#     record_reference = fields.Many2one('stock.picking', 'Record Reference', store=True, ondelete='set null', 
#                                       readonly=True, index=True)

#     active = fields.Boolean(string="active", default=True)
#     # Adjusted document - this replaces the original reference for computations
#     readjustment_document = fields.Many2one('stock.picking', string="Adjusted Document Reference", 
#                                           ondelete='set null', readonly=True, index=True,
#                                           help="When set, this document replaces the original reference for all calculations")
    
#     # Effective document - computed field that returns either adjusted or original reference
#     effective_document = fields.Many2one('stock.picking', string="Effective Document", 
#                                        compute='_compute_effective_document', store=True,
#                                        help="The document used for all calculations (adjusted if available, otherwise original)")
#     operation_type_id = fields.Many2one(string="Operation Type", related="effective_document.picking_type_id", store=True)
#     # Storage operation fields
#     pallets_received = fields.Float(store=True, string="Pallets Received", readonly=True)
#     pallets_withdrawn = fields.Float(store=True, string="Pallets Withdrawn", readonly=True)
#     kilos_received = fields.Float(store=True, string="Kilos Received", readonly=True)
#     kilos_withdrawn = fields.Float(store=True, string="Kilos Withdrawn", readonly=True)
    
#     # Computed fields with storage
#     packaging_received = fields.Float(string="Packaging Received", readonly=True, 
#                                     store=True, compute="_compute_operations")
#     packaging_withdrawn = fields.Float(string="Packaging Withdrawn", readonly=True, 
#                                      store=True, compute="_compute_operations")
#     units_received = fields.Float(string="Units Received", readonly=True, 
#                                 store=True, compute="_compute_operations")
#     units_withdrawn = fields.Float(string="Units Withdrawn", readonly=True, 
#                                  store=True, compute="_compute_operations")

#     # Balance fields with storage
#     total_balance_in_units = fields.Float(store=True, string="Total Balance in Units", readonly=True)
#     total_balance_in_packaging = fields.Float(store=True, string="Total Balance in Packaging", readonly=True)
#     total_balance_in_kilos = fields.Float(store=True, string="Total Balance in Kilos (KG)", readonly=True)
#     total_balance_in_pallets = fields.Float(store=True, string="Total Balance in Pallets", readonly=True)

#     # Return fields with storage
#     return_id = fields.Many2one('stock.picking', readonly=True, compute="_compute_returns", string="Return RR ID")
#     return_heads = fields.Float(string="Total Return Units", readonly=True, 
#                                compute="_compute_returns")
#     return_packaging = fields.Float(string="Total Return Packaging", readonly=True, 
#                                    compute="_compute_returns")
#     return_pallets = fields.Float(string="Total Return Pallets", readonly=True, 
#                                  compute="_compute_returns")
#     return_kilos = fields.Float(string="Total Return Kilos", readonly=True, 
#                                compute="_compute_returns")
    
#     # Beginning balance fields with storage
#     beginning_balance_in_pallets = fields.Float(string="Beginning Balance in Pallets", 
#                                              readonly=True, store=True, compute="_compute_beginning_balance")
#     beginning_balance_in_kilos = fields.Float(string="Beginning Balance in Kilos", 
#                                            readonly=True, store=True, compute="_compute_beginning_balance")
    
#     # Rate fields
#     holding_rate = fields.Float(string='Holding Rate', related='owner_id.x_studio_holding_rate', store=True)
#     handling_rate = fields.Float(string='Handling Rate', related='owner_id.x_studio_handling_rate', store=True)
    
#     # Vehicle fields with storage - populated from effective document
#     truck_type = fields.Selection(
#         selection=[
#             ('4wheeler', '4 Wheeler'),
#             ('6wheeler', '6 Wheeler'),
#             ('10wheeler', '10 Wheeler'),
#             ('20ft_container', '20ft Container'),
#             ('40ft_container', '40ft Container'),
#             ('N/A', 'N/A')
#         ],
#         string="Truck Type", readonly=True, store=True
#     )
#     trucks_plate = fields.Char(string="Truck's Plate #", readonly=True, store=True)
#     gate_pass = fields.Char(string="Gate Pass #", readonly=True, store=True)
#     start_time = fields.Datetime(string="Start Time", readonly=True, store=True)
#     end_time = fields.Datetime(string="End Time", readonly=True, store=True)
#     # Maximum values
#     max_pallets = fields.Many2one('x_inventory_static_var', 'Max Pallets', 
#                                  default=lambda self: self._get_static_var('Max Pallets'))
#     max_kg = fields.Many2one('x_inventory_static_var', 'Max Kilograms', 
#                            default=lambda self: self._get_static_var('Max Kilograms'))


#     # New computed fields for running balance
#     overall_pallets = fields.Float(
#         string='Overall Pallets',
#         compute='_compute_overall_balance',
#         # store=True
#     )
    
#     overall_kilos = fields.Float(
#         string='Overall Kilos',
#         compute='_compute_overall_balance',
#         # store=True
#     )

#     def resync_all(self):
#         # all_records = self.search([], order='start_time asc')
#         for record in self:
#             record._set_default_values_from_document(record.effective_document)
#             record._compute_overall_balance()
#             record._compute_beginning_balance()
#             record._compute_operations()
#             record._compute_returns()

#     def resync_all_2(self):
#         all_records = self.search([], order='start_time asc')
#         for record in all_records:
#             record._set_default_values_from_document(record.effective_document)
#             record._compute_overall_balance()
#             record._compute_beginning_balance()
#             record._compute_operations()
#             record._compute_returns()
            
#     @api.depends('warehouse', 'pallets_received', 'pallets_withdrawn', 
#                  'kilos_received', 'kilos_withdrawn')
#     def _compute_overall_balance(self):
#         for record in self:
#             # Get all records for the same warehouse up to current record's date
#             previous_records = self.search([
#                 ('record_reference.x_studio_is_a_blast_freezer', '=',  record.record_reference.x_studio_is_a_blast_freezer),
#                 ('warehouse', '=', record.warehouse.id),
#                 ('start_time', '<=', record.start_time),
#                 # ('id', '<=', record.id)
#             ], order='start_time asc, id asc')
            
#             # Calculate running totals
#             total_pallets = sum(rec.pallets_received - rec.pallets_withdrawn for rec in previous_records)
#             total_kilos = sum(rec.kilos_received - rec.kilos_withdrawn for rec in previous_records)
            
#             record.overall_pallets = total_pallets
#             record.overall_kilos = total_kilos
            
#     @api.model
#     def _get_static_var(self, var_name):
#         """Get static variable from inventory_static_var model by name"""
#         return self.env['x_inventory_static_var'].search([
#             ('x_studio_use_case', '=', 'XLSX Variables'),
#             ('x_name', 'ilike', var_name)
#         ], limit=1)

#     @api.depends('record_reference', 'readjustment_document')
#     def _compute_effective_document(self):
#         """Compute the effective document to use for calculations"""
#         for record in self:
#             # Use adjusted document if available, otherwise use original reference
#             record.effective_document = record.readjustment_document or record.record_reference

#     def _set_default_values_from_document(self, document):
#         """Set truck type, plate and gate pass values from document"""
#         if document:
#             self.truck_type = document.truck_type
#             self.trucks_plate = document.x_studio_trucks_plate_
#             self.gate_pass = document.x_studio_gate_pass
#             self.start_time = document.x_studio_start_time
#             self.end_time = document.x_studio_end_time
#         else:
#             self._clear_default_values()
    
#     def _clear_default_values(self):
#         """Clear default values"""
#         self.truck_type = False
#         self.trucks_plate = False
#         self.gate_pass = False

#     @api.model
#     def create(self, vals):
#         """Override create to set default values on creation"""
#         record = super(PalletKilosRecordModel, self).create(vals)
        
#         # Set default values from the effective document
#         effective_doc = record.readjustment_document or record.record_reference
#         if effective_doc:
#             record._set_default_values_from_document(effective_doc)
        
#         return record

#     def write(self, vals):
#         """Override write to update default values when documents change"""
#         result = super(PalletKilosRecordModel, self).write(vals)
        
#         # If either document was updated, refresh default values
#         if 'record_reference' in vals or 'readjustment_document' in vals:
#             for record in self:
#                 effective_doc = record.readjustment_document or record.record_reference
#                 if effective_doc:
#                     record._set_default_values_from_document(effective_doc)
#                 else:
#                     record._clear_default_values()
        
#         return result
    
#     @api.depends('effective_document')
#     def _compute_operations(self):
#         """Compute packaging and units operations using effective document"""
#         for record in self:
#             units_received = 0
#             units_withdrawn = 0
#             packaging_received = 0
#             packaging_withdrawn = 0
#             kilos_received = 0
#             kilos_withdrawn = 0
#             pallets = set()
#             pallet_count = 0
            
#             if record.effective_document:
#                 # Get move lines data from effective document
#                 for line in record.effective_document.move_ids_without_package:
#                     units_received += line.x_studio_min_actual_demand
#                     packaging_received += line.x_studio_actual_packaging_demand
#                     units_withdrawn += line.x_studio_min_actual_demand
#                     packaging_withdrawn += line.x_studio_actual_packaging_demand
#                     kilos_received += line.quantity
#                     kilos_withdrawn += line.quantity

#                 # Count unique pallets
#                 if record.effective_document.picking_type_id.name in ['Delivery Orders']:
#                     for move_line in record.effective_document.move_line_ids:
#                         if move_line.picking_id.x_studio_is_a_blast_freezer:
#                             if move_line.bf_pallet_char not in pallets:
#                                 pallet_count += 1
#                                 pallets.add(move_line.bf_pallet_char)
#                         else:
#                             if move_line.package_id and move_line.package_id.id not in pallets:               
#                                 package_id_record = self.env['stock.quant.package'].browse(move_line.package_id.id)
#                                 # total_quantity = sum(package_id_record.quant_ids.mapped('quantity'))
#                                 if move_line.reserved_quantity_on_validation == 0:
#                                     pallet_count += 1
#                                     pallets.add(move_line.package_id.id)
#                 else:
#                     for move_line in record.effective_document.move_line_ids:
#                         if move_line.picking_id.x_studio_is_a_blast_freezer:
#                             if move_line.bf_pallet_char not in pallets:
#                                 pallet_count += 1
#                                 pallets.add(move_line.bf_pallet_char)
#                         else:
#                             if move_line.result_package_id and move_line.result_package_id.id not in pallets:
#                                 pallet_count += 1
#                                 pallets.add(move_line.result_package_id.id)
                        
#                 # Set values based on picking type
#                 picking_code = record.effective_document.picking_type_id.code
                
#                 if picking_code == 'incoming':
#                     record.units_received = units_received
#                     record.packaging_received = packaging_received
#                     record.kilos_received = kilos_received
#                     record.pallets_received = pallet_count
#                     record.units_withdrawn = 0
#                     record.packaging_withdrawn = 0
#                     record.kilos_withdrawn = 0
#                     record.pallets_withdrawn = 0
                
#                 elif picking_code == 'outgoing':
#                     record.units_withdrawn = units_withdrawn
#                     record.packaging_withdrawn = packaging_withdrawn
#                     record.kilos_withdrawn = kilos_withdrawn
#                     record.pallets_withdrawn = pallet_count
#                     record.units_received = 0
#                     record.packaging_received = 0
#                     record.kilos_received = 0
#                     record.pallets_received = 0
                
#                 else:
#                     # Neutral state for other types
#                     record.units_received = 0
#                     record.packaging_received = 0
#                     record.units_withdrawn = 0
#                     record.packaging_withdrawn = 0
#                     record.kilos_received = 0
#                     record.kilos_withdrawn = 0
#                     record.pallets_received = 0
#                     record.pallets_withdrawn = 0
#             else:
#                 # Clear all values if no effective document
#                 record.units_received = 0
#                 record.packaging_received = 0
#                 record.units_withdrawn = 0
#                 record.packaging_withdrawn = 0
#                 record.kilos_received = 0
#                 record.kilos_withdrawn = 0
#                 record.pallets_received = 0
#                 record.pallets_withdrawn = 0
    
#     @api.depends('effective_document')
#     def _compute_returns(self):
#         """Compute return values using effective document"""
#         for record in self:
#             return_heads = 0
#             return_packaging = 0
#             return_pallets = 0
#             return_kilos = 0
#             pallets = set()
            
#             # Default value to avoid compute error
#             record.return_id = False
    
#             if record.effective_document:
#                 for returns in record.effective_document.return_ids:
#                     if returns.state == 'done' and returns.return_reason == 'Partial Withdraw' and not returns.x_studio_voided:
#                         record.return_id = returns.id
#                         for line_ids in returns.move_line_ids:
#                             return_heads += line_ids.x_studio_total_units
#                             return_packaging += line_ids.x_studio_2nd_uom
#                             return_kilos += line_ids.quantity
#                             if line_ids.result_package_id and line_ids.result_package_id.id not in pallets:
#                                 return_pallets += 1
#                                 pallets.add(line_ids.result_package_id.id)
#                         break  # break after first matching return
    
#             record.return_heads = return_heads
#             record.return_packaging = return_packaging
#             record.return_pallets = return_pallets
#             record.return_kilos = return_kilos
    
#     @api.depends('owner_id', 'effective_document.picking_type_id.name')
#     def _compute_beginning_balance(self):
#         """Compute beginning balance values using effective document"""
#         for record in self:
#             # Initialize values
#             record.beginning_balance_in_pallets = 0.0
#             record.beginning_balance_in_kilos = 0.0
            
#             if not record.owner_id or not record.effective_document:
#                 continue
            
#             # Determine record type category
#             picking_type_name = record.effective_document.picking_type_id.name
#             category = None
            
#             if picking_type_name in ['Receipts', 'Delivery Orders']:
#                 category = ['Receipts', 'Delivery Orders']
#             elif picking_type_name in ['Blast Freeze - IN', 'Blast Freeze - OUT']:
#                 category = ['Blast Freeze - IN', 'Blast Freeze - OUT']
            
#             if category:
#                 # Search for previous records in this category
#                 prev = self.search([
#                     ('owner_id', '=', record.owner_id.id),
#                     ('start_time', '<', record.start_time),
#                     # ('effective_document.picking_type_id.name', 'in', category)
#                 ], order='start_time desc', limit=1)
                
#                 # Ensure operations are computed
#                 record._compute_operations()
#                 # begin - begin + rr - wr
#                 # Set beginning balances from previous record
#                 if prev:
#                     record.beginning_balance_in_pallets = prev.total_balance_in_pallets
#                     record.beginning_balance_in_kilos = prev.total_balance_in_kilos

#                     if record.effective_document.picking_type_id.code == 'outgoing':
#                         record.total_balance_in_packaging = prev.total_balance_in_packaging - record.packaging_withdrawn
#                         record.total_balance_in_units = prev.total_balance_in_units - record.units_withdrawn
#                         record.total_balance_in_kilos = prev.total_balance_in_kilos - record.kilos_withdrawn
#                         record.total_balance_in_pallets = prev.total_balance_in_pallets - record.pallets_withdrawn
#                     elif record.effective_document.picking_type_id.code == 'incoming':
#                         record.total_balance_in_packaging = prev.total_balance_in_packaging + record.packaging_received
#                         record.total_balance_in_units = prev.total_balance_in_units + record.units_received
#                         record.total_balance_in_kilos = prev.total_balance_in_kilos + record.kilos_received
#                         record.total_balance_in_pallets = prev.total_balance_in_pallets + record.pallets_received
#                 else:
#                     # First record - set beginning balance to 0 and total balance to received amounts
#                     record.beginning_balance_in_pallets = 0
#                     record.beginning_balance_in_kilos = 0
#                     record.total_balance_in_packaging = record.packaging_received
#                     record.total_balance_in_units = record.units_received
#                     record.total_balance_in_kilos = record.kilos_received
#                     record.total_balance_in_pallets = record.pallets_received

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class PalletKilosRecordModel(models.Model):
    _name = 'pallet_kilos_record_model.pallet_kilos_record_model'
    _description = 'Pallet Kilos Record Model'
    _order = 'start_time asc, id asc'  # Consistent ordering for running balance
    
    # Basic identification fields
    report_no = fields.Char(string="Report No.", readonly=True, index=True)
    owner_id = fields.Many2one('res.partner', 'Owner', ondelete='set null', readonly=True, index=True)
    warehouse = fields.Many2one('stock.warehouse', 'Warehouse', ondelete='set null', readonly=True, index=True)
    record_reference = fields.Many2one('stock.picking', 'Record Reference', store=True, ondelete='set null', 
                                      readonly=True, index=True)

    active = fields.Boolean(string="Active", default=True, index=True)
    
    # Adjusted document - this replaces the original reference for computations
    readjustment_document = fields.Many2one('stock.picking', string="Adjusted Document Reference", 
                                          ondelete='set null', readonly=True, index=True,
                                          help="When set, this document replaces the original reference for all calculations")
    
    # Effective document - computed field that returns either adjusted or original reference
    effective_document = fields.Many2one('stock.picking', string="Effective Document", 
                                       compute='_compute_effective_document', store=True,
                                       help="The document used for all calculations (adjusted if available, otherwise original)")
    
    operation_type_id = fields.Many2one(string="Operation Type", related="effective_document.picking_type_id", store=True)
    
    # Storage operation fields - these should be computed, not stored separately
    pallets_received = fields.Float(string="Pallets Received", compute='_compute_operations', store=True)
    pallets_withdrawn = fields.Float(string="Pallets Withdrawn", compute='_compute_operations', store=True)
    kilos_received = fields.Float(string="Kilos Received", compute='_compute_operations', store=True)
    kilos_withdrawn = fields.Float(string="Kilos Withdrawn", compute='_compute_operations', store=True)
    
    # Computed fields with storage
    packaging_received = fields.Float(string="Packaging Received", compute="_compute_operations", store=True)
    packaging_withdrawn = fields.Float(string="Packaging Withdrawn", compute="_compute_operations", store=True)
    units_received = fields.Float(string="Units Received", compute="_compute_operations", store=True)
    units_withdrawn = fields.Float(string="Units Withdrawn", compute="_compute_operations", store=True)

    # Balance fields - these will be computed based on running totals
    total_balance_in_units = fields.Float(string="Total Balance in Units", compute='_compute_running_balance', store=True)
    total_balance_in_packaging = fields.Float(string="Total Balance in Packaging", compute='_compute_running_balance', store=True)
    total_balance_in_kilos = fields.Float(string="Total Balance in Kilos (KG)", compute='_compute_running_balance', store=True)
    total_balance_in_pallets = fields.Float(string="Total Balance in Pallets", compute='_compute_running_balance', store=True)

    # Return fields
    return_id = fields.Many2one('stock.picking', compute="_compute_returns", store=True, string="Return RR ID")
    return_heads = fields.Float(string="Total Return Units", compute="_compute_returns", store=True)
    return_packaging = fields.Float(string="Total Return Packaging", compute="_compute_returns", store=True)
    return_pallets = fields.Float(string="Total Return Pallets", compute="_compute_returns", store=True)
    return_kilos = fields.Float(string="Total Return Kilos", compute="_compute_returns", store=True)
    
    # Beginning balance fields
    beginning_balance_in_pallets = fields.Float(string="Beginning Balance in Pallets", 
                                             compute="_compute_running_balance", store=True)
    beginning_balance_in_kilos = fields.Float(string="Beginning Balance in Kilos", 
                                           compute="_compute_running_balance", store=True)
    beginning_balance_in_units = fields.Float(string="Beginning Balance in Units", 
                                           compute="_compute_running_balance", store=True)
    beginning_balance_in_packaging = fields.Float(string="Beginning Balance in Packaging", 
                                                 compute="_compute_running_balance", store=True)
    
    # Rate fields
    holding_rate = fields.Float(string='Holding Rate', related='owner_id.x_studio_holding_rate', store=True)
    handling_rate = fields.Float(string='Handling Rate', related='owner_id.x_studio_handling_rate', store=True)
    
    # Vehicle fields - populated from effective document
    truck_type = fields.Selection(
        selection=[
            ('4wheeler', '4 Wheeler'),
            ('6wheeler', '6 Wheeler'),
            ('10wheeler', '10 Wheeler'),
            ('20ft_container', '20ft Container'),
            ('40ft_container', '40ft Container'),
            ('N/A', 'N/A')
        ],
        string="Truck Type", compute='_compute_vehicle_info', store=True
    )
    trucks_plate = fields.Char(string="Truck's Plate #", compute='_compute_vehicle_info', store=True)
    gate_pass = fields.Char(string="Gate Pass #", compute='_compute_vehicle_info', store=True)
    start_time = fields.Datetime(string="Start Time", compute='_compute_vehicle_info', store=True, index=True)
    end_time = fields.Datetime(string="End Time", compute='_compute_vehicle_info', store=True)
    
    # Blast freezer flag for efficient filtering
    is_blast_freezer = fields.Boolean(string="Is Blast Freezer", compute='_compute_vehicle_info', store=True, index=True)
    
    # Maximum values
    max_pallets = fields.Many2one('x_inventory_static_var', 'Max Pallets', 
                                 default=lambda self: self._get_static_var('Max Pallets'))
    max_kg = fields.Many2one('x_inventory_static_var', 'Max Kilograms', 
                           default=lambda self: self._get_static_var('Max Kilograms'))

    # Running balance fields (from original code)
    overall_pallets = fields.Float(
        string='Overall Pallets',
        compute='_compute_overall_balance',
        store=True
    )
    
    overall_kilos = fields.Float(
        string='Overall Kilos',
        compute='_compute_overall_balance',
        store=True
    )

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

    @api.depends('effective_document')
    def _compute_vehicle_info(self):
        """Compute vehicle and timing information from effective document"""
        for record in self:
            if record.effective_document:
                doc = record.effective_document
                record.truck_type = doc.truck_type
                record.trucks_plate = doc.x_studio_trucks_plate_
                record.gate_pass = doc.x_studio_gate_pass
                record.start_time = doc.x_studio_start_time
                record.end_time = doc.x_studio_end_time
                record.is_blast_freezer = doc.x_studio_is_a_blast_freezer
            else:
                record.truck_type = False
                record.trucks_plate = False
                record.gate_pass = False
                record.start_time = False
                record.end_time = False
                record.is_blast_freezer = False

    @api.depends('effective_document', 'effective_document.move_ids_without_package', 'effective_document.move_line_ids')
    def _compute_operations(self):
        """Compute all operation values from effective document"""
        for record in self:
            # Initialize all values
            values = {
                'units_received': 0, 'units_withdrawn': 0,
                'packaging_received': 0, 'packaging_withdrawn': 0,
                'kilos_received': 0, 'kilos_withdrawn': 0,
                'pallets_received': 0, 'pallets_withdrawn': 0
            }
            
            if not record.effective_document:
                # Set all values to 0
                for field, value in values.items():
                    setattr(record, field, value)
                continue
            
            doc = record.effective_document
            picking_code = doc.picking_type_id.code
            
            # Calculate units, packaging, and kilos from move lines
            total_units = sum(line.x_studio_min_actual_demand for line in doc.move_ids_without_package)
            total_packaging = sum(line.x_studio_actual_packaging_demand for line in doc.move_ids_without_package)
            total_kilos = sum(line.quantity for line in doc.move_ids_without_package)
            
            # Calculate pallets
            pallet_count = self._calculate_pallet_count(doc)
            
            # Set values based on operation type
            if picking_code == 'incoming':
                values.update({
                    'units_received': total_units,
                    'packaging_received': total_packaging,
                    'kilos_received': total_kilos,
                    'pallets_received': pallet_count
                })
            elif picking_code == 'outgoing':
                values.update({
                    'units_withdrawn': total_units,
                    'packaging_withdrawn': total_packaging,
                    'kilos_withdrawn': total_kilos,
                    'pallets_withdrawn': pallet_count
                })
            
            # Apply all values at once
            for field, value in values.items():
                setattr(record, field, value)

    def _calculate_pallet_count(self, document):
        """Calculate unique pallet count from document move lines"""
        pallets = set()
        
        for move_line in document.move_line_ids:
            if document.x_studio_is_a_blast_freezer:
                # Blast freezer logic
                if move_line.bf_pallet_char:
                    pallets.add(move_line.bf_pallet_char)
            else:
                # Regular warehouse logic
                if document.picking_type_id.name == 'Delivery Orders':
                    if (move_line.package_id and 
                        move_line.reserved_quantity_on_validation == 0):
                        pallets.add(move_line.package_id.id)
                else:
                    if move_line.result_package_id:
                        pallets.add(move_line.result_package_id.id)
        
        return len(pallets)

    @api.depends('effective_document', 'effective_document.return_ids')
    def _compute_returns(self):
        """Compute return values from effective document"""
        for record in self:
            # Initialize values
            record.return_id = False
            record.return_heads = 0
            record.return_packaging = 0
            record.return_pallets = 0
            record.return_kilos = 0
            
            if not record.effective_document:
                continue
            
            # Find the first matching return
            for return_doc in record.effective_document.return_ids:
                if (return_doc.state == 'done' and 
                    return_doc.return_reason == 'Partial Withdraw' and 
                    not return_doc.x_studio_voided):
                    
                    record.return_id = return_doc.id
                    
                    # Calculate return values
                    pallets = set()
                    for line in return_doc.move_line_ids:
                        record.return_heads += line.x_studio_total_units
                        record.return_packaging += line.x_studio_2nd_uom
                        record.return_kilos += line.quantity
                        
                        if line.result_package_id and line.result_package_id.id not in pallets:
                            pallets.add(line.result_package_id.id)
                    
                    record.return_pallets = len(pallets)
                    break

    @api.depends('owner_id', 'warehouse', 'is_blast_freezer', 'start_time',
                 'units_received', 'units_withdrawn', 'packaging_received', 'packaging_withdrawn',
                 'kilos_received', 'kilos_withdrawn', 'pallets_received', 'pallets_withdrawn')
    def _compute_running_balance(self):
        """Compute running balance efficiently using bulk operations"""
        if not self:
            return
        
        # Group records by key factors for efficient processing
        grouped_records = {}
        for record in self:
            if not record.owner_id or not record.warehouse:
                # Set default values for incomplete records
                record._set_zero_balances()
                continue
                
            key = (record.owner_id.id, record.warehouse.id, record.is_blast_freezer)
            if key not in grouped_records:
                grouped_records[key] = []
            grouped_records[key].append(record)
        
        # Process each group
        for key, records in grouped_records.items():
            self._compute_group_running_balance(records)

    def _set_zero_balances(self):
        """Set all balance fields to zero"""
        self.beginning_balance_in_units = 0
        self.beginning_balance_in_packaging = 0
        self.beginning_balance_in_kilos = 0
        self.beginning_balance_in_pallets = 0
        self.total_balance_in_units = 0
        self.total_balance_in_packaging = 0
        self.total_balance_in_kilos = 0
        self.total_balance_in_pallets = 0

    def _compute_group_running_balance(self, records):
        """Compute running balance for a group of records with same owner/warehouse"""
        # Sort records by start_time and id for consistent processing
        sorted_records = sorted(records, key=lambda r: (r.start_time or datetime.min, r.id))
        
        # Initialize running totals
        running_units = 0
        running_packaging = 0  
        running_kilos = 0
        running_pallets = 0
        
        for record in sorted_records:
            # Set beginning balance (state before this record)
            record.beginning_balance_in_units = running_units
            record.beginning_balance_in_packaging = running_packaging
            record.beginning_balance_in_kilos = running_kilos
            record.beginning_balance_in_pallets = running_pallets
            
            # Update running totals with this record's operations
            running_units += (record.units_received - record.units_withdrawn)
            running_packaging += (record.packaging_received - record.packaging_withdrawn)
            running_kilos += (record.kilos_received - record.kilos_withdrawn)
            running_pallets += (record.pallets_received - record.pallets_withdrawn)
            
            # Set total balance (state after this record)
            record.total_balance_in_units = running_units
            record.total_balance_in_packaging = running_packaging
            record.total_balance_in_kilos = running_kilos
            record.total_balance_in_pallets = running_pallets

    def action_recalculate_all_balances(self):
        """Manual action to recalculate all balances - use with caution"""
        _logger.info("Starting manual recalculation of all balances")
        
        # Get all active records ordered by time
        all_records = self.search([('active', '=', True)], order='start_time asc, id asc')
        
        # Process in batches to avoid timeout
        batch_size = 100
        for i in range(0, len(all_records), batch_size):
            batch = all_records[i:i+batch_size]
            batch._compute_running_balance()
            
            # Commit after each batch
            if i % (batch_size * 5) == 0:  # Every 5 batches
                self.env.cr.commit()
                _logger.info(f"Processed {i + len(batch)} records")
        
        _logger.info("Completed recalculation of all balances")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Successfully recalculated balances for {len(all_records)} records',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def create(self, vals):
        """Override create to trigger balance recalculation for affected records"""
        record = super().create(vals)
        
        # Trigger recalculation for subsequent records in the same group
        if record.owner_id and record.warehouse and record.start_time:
            self._trigger_balance_recalculation(record)
        
        return record

    def write(self, vals):
        """Override write to trigger balance recalculation when relevant fields change"""
        # Store old values that might affect balance calculation
        old_values = []
        balance_affecting_fields = [
            'owner_id', 'warehouse', 'start_time', 'effective_document', 
            'record_reference', 'readjustment_document'
        ]
        
        if any(field in vals for field in balance_affecting_fields):
            for record in self:
                old_values.append({
                    'record': record,
                    'owner_id': record.owner_id.id if record.owner_id else False,
                    'warehouse': record.warehouse.id if record.warehouse else False,
                    'start_time': record.start_time,
                    'is_blast_freezer': record.is_blast_freezer
                })
        
        result = super().write(vals)
        
        # Trigger recalculation for affected records
        if old_values:
            for old_val in old_values:
                self._trigger_balance_recalculation(old_val['record'])
                
                # If key fields changed, also recalculate old group
                if (vals.get('owner_id') != old_val['owner_id'] or 
                    vals.get('warehouse') != old_val['warehouse'] or
                    'start_time' in vals):
                    self._trigger_balance_recalculation_for_group(
                        old_val['owner_id'], 
                        old_val['warehouse'], 
                        old_val['is_blast_freezer'],
                        old_val['start_time']
                    )
        
        return result

    def _trigger_balance_recalculation(self, record):
        """Trigger balance recalculation for records that might be affected"""
        if not record.owner_id or not record.warehouse:
            return
        
        # Find all records in the same group that come after this record
        subsequent_records = self.search([
            ('owner_id', '=', record.owner_id.id),
            ('warehouse', '=', record.warehouse.id),
            ('is_blast_freezer', '=', record.is_blast_freezer),
            ('start_time', '>=', record.start_time),
            ('active', '=', True)
        ], order='start_time asc, id asc')
        
        if subsequent_records:
            subsequent_records._compute_running_balance()

    def _trigger_balance_recalculation_for_group(self, owner_id, warehouse_id, is_blast_freezer, from_time):
        """Trigger balance recalculation for a specific group from a given time"""
        if not owner_id or not warehouse_id:
            return
        
        affected_records = self.search([
            ('owner_id', '=', owner_id),
            ('warehouse', '=', warehouse_id),
            ('is_blast_freezer', '=', is_blast_freezer),
            ('start_time', '>=', from_time),
            ('active', '=', True)
        ], order='start_time asc, id asc')
        
        if affected_records:
            affected_records._compute_running_balance()

    @api.depends('warehouse', 'pallets_received', 'pallets_withdrawn', 
                 'kilos_received', 'kilos_withdrawn', 'is_blast_freezer')
    def _compute_overall_balance(self):
        """Compute overall balance (alternative running balance method from original code)"""
        for record in self:
            if not record.warehouse or not record.start_time:
                record.overall_pallets = 0
                record.overall_kilos = 0
                continue
                
            # Get all records for the same warehouse up to current record's date
            previous_records = self.search([
                ('is_blast_freezer', '=', record.is_blast_freezer),
                ('warehouse', '=', record.warehouse.id),
                ('start_time', '<=', record.start_time),
                ('active', '=', True)
            ], order='start_time asc, id asc')
            
            # Calculate running totals
            total_pallets = sum(rec.pallets_received - rec.pallets_withdrawn for rec in previous_records)
            total_kilos = sum(rec.kilos_received - rec.kilos_withdrawn for rec in previous_records)
            
            record.overall_pallets = total_pallets
            record.overall_kilos = total_kilos



    def unlink(self):
        """Override unlink to trigger balance recalculation for affected records"""
        # Store information about records that will be deleted
        deleted_info = []
        for record in self:
            if record.owner_id and record.warehouse and record.start_time:
                deleted_info.append({
                    'owner_id': record.owner_id.id,
                    'warehouse': record.warehouse.id,
                    'is_blast_freezer': record.is_blast_freezer,
                    'start_time': record.start_time
                })
        
        result = super().unlink()
        
        # Trigger recalculation for affected groups
        for info in deleted_info:
            self._trigger_balance_recalculation_for_group(
                info['owner_id'], 
                info['warehouse'], 
                info['is_blast_freezer'],
                info['start_time']
            )
        
        return result