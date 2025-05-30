import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from models import Machine, MachineSlot, ProductionPlan, CapacityPlan, get_session
from sqlalchemy import desc, and_
import datetime
import requests
import json
import sys
import os

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import GRAPHQL_ENDPOINTS

# Define GraphQL types
class MachineType(SQLAlchemyObjectType):
    class Meta:
        model = Machine
        interfaces = (relay.Node, )

class MachineSlotType(SQLAlchemyObjectType):
    class Meta:
        model = MachineSlot
        interfaces = (relay.Node, )

class ProductionPlanType(SQLAlchemyObjectType):
    class Meta:
        model = ProductionPlan
        interfaces = (relay.Node, )
    
    # Add custom field for materials
    required_materials = graphene.List(graphene.String)
    
    def resolve_required_materials(self, info):
        # This would typically call the Material Inventory Service GraphQL API
        # For now, we'll return a placeholder
        return [f"Material {i} for Plan {self.id}" for i in range(1, 4)]

class CapacityPlanType(SQLAlchemyObjectType):
    class Meta:
        model = CapacityPlan
        interfaces = (relay.Node, )

# Input types for mutations
class MachineInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    machine_type = graphene.String()
    status = graphene.String()
    capacity_per_hour = graphene.Float()

class MachineSlotInput(graphene.InputObjectType):
    machine_id = graphene.Int(required=True)
    start_time = graphene.DateTime(required=True)
    end_time = graphene.DateTime(required=True)
    status = graphene.String()
    production_plan_id = graphene.Int()

class ProductionPlanInput(graphene.InputObjectType):
    name = graphene.String()
    product_id = graphene.Int(required=True)
    quantity = graphene.Int(required=True)
    priority = graphene.Int()
    status = graphene.String()
    start_date = graphene.DateTime()
    end_date = graphene.DateTime()
    material_requirements = graphene.List(graphene.String)  # Format: "material_id:quantity"

class CapacityPlanInput(graphene.InputObjectType):
    name = graphene.String()
    period_start = graphene.DateTime(required=True)
    period_end = graphene.DateTime(required=True)
    total_capacity_hours = graphene.Float()
    allocated_capacity_hours = graphene.Float()
    notes = graphene.String()

# Check material availability from Material Inventory Service
def check_material_availability(material_id, quantity_needed):
    try:
        # GraphQL query to check material availability
        query = """
        query($id: Int!) {
            material(id: $id) {
                id
                name
                quantity
            }
        }
        """
        variables = {"id": material_id}
        
        # Make request to Material Inventory Service
        response = requests.post(
            GRAPHQL_ENDPOINTS["material_inventory"],
            json={"query": query, "variables": variables}
        )
        
        data = response.json()
        if 'data' in data and 'material' in data['data'] and data['data']['material']:
            available_quantity = data['data']['material']['quantity']
            return available_quantity >= quantity_needed
        
        return False
    except Exception as e:
        print(f"Error checking material availability: {e}")
        return False

# Mutations
class CreateMachine(graphene.Mutation):
    class Arguments:
        input = MachineInput(required=True)
    
    machine = graphene.Field(lambda: MachineType)
    
    def mutate(self, info, input):
        session = get_session()
        machine = Machine(
            name=input.name,
            machine_type=input.machine_type,
            status=input.status or 'available',
            capacity_per_hour=input.capacity_per_hour
        )
        session.add(machine)
        session.commit()
        session.refresh(machine)
        session.close()
        return CreateMachine(machine=machine)

class UpdateMachine(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = MachineInput(required=True)
    
    machine = graphene.Field(lambda: MachineType)
    
    def mutate(self, info, id, input):
        session = get_session()
        machine = session.query(Machine).filter(Machine.id == id).first()
        
        if machine:
            machine.name = input.name
            machine.machine_type = input.machine_type
            machine.status = input.status or machine.status
            machine.capacity_per_hour = input.capacity_per_hour
            
            session.commit()
            session.refresh(machine)
        
        session.close()
        return UpdateMachine(machine=machine)

class DeleteMachine(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    
    def mutate(self, info, id):
        session = get_session()
        machine = session.query(Machine).filter(Machine.id == id).first()
        
        if machine:
            session.delete(machine)
            session.commit()
            success = True
        else:
            success = False
        
        session.close()
        return DeleteMachine(success=success)

class CreateMachineSlot(graphene.Mutation):
    class Arguments:
        input = MachineSlotInput(required=True)
    
    machine_slot = graphene.Field(lambda: MachineSlotType)
    
    def mutate(self, info, input):
        session = get_session()
        
        # Check if the machine exists
        machine = session.query(Machine).filter(Machine.id == input.machine_id).first()
        if not machine:
            raise Exception(f"Machine with ID {input.machine_id} not found")
        
        # Check if there's any overlap with existing slots
        overlapping_slots = session.query(MachineSlot).filter(
            MachineSlot.machine_id == input.machine_id,
            MachineSlot.start_time < input.end_time,
            MachineSlot.end_time > input.start_time
        ).all()
        
        if overlapping_slots:
            raise Exception("The requested time slot overlaps with existing slots")
        
        # Create new slot
        machine_slot = MachineSlot(
            machine_id=input.machine_id,
            start_time=input.start_time,
            end_time=input.end_time,
            status=input.status or 'available',
            production_plan_id=input.production_plan_id
        )
        session.add(machine_slot)
        session.commit()
        session.refresh(machine_slot)
        session.close()
        return CreateMachineSlot(machine_slot=machine_slot)

class UpdateMachineSlot(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = MachineSlotInput(required=True)
    
    machine_slot = graphene.Field(lambda: MachineSlotType)
    
    def mutate(self, info, id, input):
        session = get_session()
        machine_slot = session.query(MachineSlot).filter(MachineSlot.id == id).first()
        
        if machine_slot:
            # Check for overlaps if changing times
            if input.start_time != machine_slot.start_time or input.end_time != machine_slot.end_time:
                overlapping_slots = session.query(MachineSlot).filter(
                    MachineSlot.machine_id == input.machine_id,
                    MachineSlot.id != id,
                    MachineSlot.start_time < input.end_time,
                    MachineSlot.end_time > input.start_time
                ).all()
                
                if overlapping_slots:
                    raise Exception("The requested time slot overlaps with existing slots")
            
            machine_slot.machine_id = input.machine_id
            machine_slot.start_time = input.start_time
            machine_slot.end_time = input.end_time
            machine_slot.status = input.status or machine_slot.status
            machine_slot.production_plan_id = input.production_plan_id
            
            session.commit()
            session.refresh(machine_slot)
        
        session.close()
        return UpdateMachineSlot(machine_slot=machine_slot)

class DeleteMachineSlot(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    
    def mutate(self, info, id):
        session = get_session()
        machine_slot = session.query(MachineSlot).filter(MachineSlot.id == id).first()
        
        if machine_slot:
            session.delete(machine_slot)
            session.commit()
            success = True
        else:
            success = False
        
        session.close()
        return DeleteMachineSlot(success=success)

class CreateProductionPlan(graphene.Mutation):
    class Arguments:
        input = ProductionPlanInput(required=True)
    
    production_plan = graphene.Field(lambda: ProductionPlanType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        session = get_session()
        
        # Check material requirements if provided
        if hasattr(input, 'material_requirements') and input.material_requirements:
            all_materials_available = True
            for material_req in input.material_requirements:
                material_id, quantity = map(int, material_req.split(':'))
                if not check_material_availability(material_id, quantity):
                    all_materials_available = False
                    break
            
            if not all_materials_available:
                return CreateProductionPlan(
                    production_plan=None,
                    success=False,
                    message="Not all required materials are available in sufficient quantities"
                )
        
        # Create production plan
        production_plan = ProductionPlan(
            name=input.name or f"Plan for Product {input.product_id}",
            product_id=input.product_id,
            quantity=input.quantity,
            priority=input.priority or 1,
            status=input.status or 'draft',
            start_date=input.start_date,
            end_date=input.end_date
        )
        session.add(production_plan)
        session.commit()
        session.refresh(production_plan)
        session.close()
        
        return CreateProductionPlan(
            production_plan=production_plan,
            success=True,
            message="Production plan created successfully"
        )

class UpdateProductionPlan(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = ProductionPlanInput(required=True)
    
    production_plan = graphene.Field(lambda: ProductionPlanType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, id, input):
        session = get_session()
        production_plan = session.query(ProductionPlan).filter(ProductionPlan.id == id).first()
        
        if not production_plan:
            return UpdateProductionPlan(
                production_plan=None,
                success=False,
                message=f"Production plan with ID {id} not found"
            )
        
        # Check material requirements if provided
        if hasattr(input, 'material_requirements') and input.material_requirements:
            all_materials_available = True
            for material_req in input.material_requirements:
                material_id, quantity = map(int, material_req.split(':'))
                if not check_material_availability(material_id, quantity):
                    all_materials_available = False
                    break
            
            if not all_materials_available:
                return UpdateProductionPlan(
                    production_plan=None,
                    success=False,
                    message="Not all required materials are available in sufficient quantities"
                )
        
        # Update production plan
        production_plan.name = input.name or production_plan.name
        production_plan.product_id = input.product_id
        production_plan.quantity = input.quantity
        production_plan.priority = input.priority or production_plan.priority
        production_plan.status = input.status or production_plan.status
        production_plan.start_date = input.start_date or production_plan.start_date
        production_plan.end_date = input.end_date or production_plan.end_date
        
        session.commit()
        session.refresh(production_plan)
        session.close()
        
        return UpdateProductionPlan(
            production_plan=production_plan,
            success=True,
            message="Production plan updated successfully"
        )

class DeleteProductionPlan(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, id):
        session = get_session()
        production_plan = session.query(ProductionPlan).filter(ProductionPlan.id == id).first()
        
        if production_plan:
            # Check if plan is already in progress
            if production_plan.status in ['in_progress', 'completed']:
                return DeleteProductionPlan(
                    success=False,
                    message=f"Cannot delete production plan with status '{production_plan.status}'"
                )
            
            # Delete associated machine slots
            session.query(MachineSlot).filter(MachineSlot.production_plan_id == id).delete()
            
            # Delete the plan
            session.delete(production_plan)
            session.commit()
            return DeleteProductionPlan(
                success=True,
                message="Production plan deleted successfully"
            )
        else:
            return DeleteProductionPlan(
                success=False,
                message=f"Production plan with ID {id} not found"
            )

class CreateCapacityPlan(graphene.Mutation):
    class Arguments:
        input = CapacityPlanInput(required=True)
    
    capacity_plan = graphene.Field(lambda: CapacityPlanType)
    
    def mutate(self, info, input):
        session = get_session()
        capacity_plan = CapacityPlan(
            name=input.name or f"Capacity Plan {input.period_start.strftime('%Y-%m-%d')} to {input.period_end.strftime('%Y-%m-%d')}",
            period_start=input.period_start,
            period_end=input.period_end,
            total_capacity_hours=input.total_capacity_hours,
            allocated_capacity_hours=input.allocated_capacity_hours or 0,
            notes=input.notes
        )
        session.add(capacity_plan)
        session.commit()
        session.refresh(capacity_plan)
        session.close()
        return CreateCapacityPlan(capacity_plan=capacity_plan)

class UpdateCapacityPlan(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = CapacityPlanInput(required=True)
    
    capacity_plan = graphene.Field(lambda: CapacityPlanType)
    
    def mutate(self, info, id, input):
        session = get_session()
        capacity_plan = session.query(CapacityPlan).filter(CapacityPlan.id == id).first()
        
        if capacity_plan:
            capacity_plan.name = input.name or capacity_plan.name
            capacity_plan.period_start = input.period_start
            capacity_plan.period_end = input.period_end
            capacity_plan.total_capacity_hours = input.total_capacity_hours or capacity_plan.total_capacity_hours
            capacity_plan.allocated_capacity_hours = input.allocated_capacity_hours or capacity_plan.allocated_capacity_hours
            capacity_plan.notes = input.notes
            
            session.commit()
            session.refresh(capacity_plan)
        
        session.close()
        return UpdateCapacityPlan(capacity_plan=capacity_plan)

class DeleteCapacityPlan(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    
    def mutate(self, info, id):
        session = get_session()
        capacity_plan = session.query(CapacityPlan).filter(CapacityPlan.id == id).first()
        
        if capacity_plan:
            session.delete(capacity_plan)
            session.commit()
            success = True
        else:
            success = False
        
        session.close()
        return DeleteCapacityPlan(success=success)

class Mutation(graphene.ObjectType):
    create_machine = CreateMachine.Field()
    update_machine = UpdateMachine.Field()
    delete_machine = DeleteMachine.Field()
    
    create_machine_slot = CreateMachineSlot.Field()
    update_machine_slot = UpdateMachineSlot.Field()
    delete_machine_slot = DeleteMachineSlot.Field()
    
    create_production_plan = CreateProductionPlan.Field()
    update_production_plan = UpdateProductionPlan.Field()
    delete_production_plan = DeleteProductionPlan.Field()
    
    create_capacity_plan = CreateCapacityPlan.Field()
    update_capacity_plan = UpdateCapacityPlan.Field()
    delete_capacity_plan = DeleteCapacityPlan.Field()

# Queries
class Query(graphene.ObjectType):
    node = relay.Node.Field()
    
    # Machine queries
    machine = graphene.Field(MachineType, id=graphene.Int())
    all_machines = graphene.List(MachineType)
    machines_by_status = graphene.List(MachineType, status=graphene.String())
    
    # Machine slot queries
    machine_slot = graphene.Field(MachineSlotType, id=graphene.Int())
    machine_slots = graphene.List(MachineSlotType, machine_id=graphene.Int())
    available_slots = graphene.List(
        MachineSlotType,
        start_time=graphene.DateTime(),
        end_time=graphene.DateTime()
    )
    
    # Production plan queries
    production_plan = graphene.Field(ProductionPlanType, id=graphene.Int())
    all_production_plans = graphene.List(ProductionPlanType)
    production_plans_by_status = graphene.List(ProductionPlanType, status=graphene.String())
    
    # Capacity plan queries
    capacity_plan = graphene.Field(CapacityPlanType, id=graphene.Int())
    all_capacity_plans = graphene.List(CapacityPlanType)
    capacity_plans_by_date = graphene.List(
        CapacityPlanType,
        date=graphene.DateTime()
    )
    
    def resolve_machine(self, info, id):
        session = get_session()
        machine = session.query(Machine).filter(Machine.id == id).first()
        session.close()
        return machine
    
    def resolve_all_machines(self, info):
        session = get_session()
        machines = session.query(Machine).all()
        session.close()
        return machines
    
    def resolve_machines_by_status(self, info, status):
        session = get_session()
        machines = session.query(Machine).filter(Machine.status == status).all()
        session.close()
        return machines
    
    def resolve_machine_slot(self, info, id):
        session = get_session()
        slot = session.query(MachineSlot).filter(MachineSlot.id == id).first()
        session.close()
        return slot
    
    def resolve_machine_slots(self, info, machine_id):
        session = get_session()
        slots = session.query(MachineSlot).filter(MachineSlot.machine_id == machine_id).all()
        session.close()
        return slots
    
    def resolve_available_slots(self, info, start_time=None, end_time=None):
        session = get_session()
        query = session.query(MachineSlot).filter(MachineSlot.status == 'available')
        
        if start_time:
            query = query.filter(MachineSlot.start_time >= start_time)
        
        if end_time:
            query = query.filter(MachineSlot.end_time <= end_time)
        
        slots = query.all()
        session.close()
        return slots
    
    def resolve_production_plan(self, info, id):
        session = get_session()
        plan = session.query(ProductionPlan).filter(ProductionPlan.id == id).first()
        session.close()
        return plan
    
    def resolve_all_production_plans(self, info):
        session = get_session()
        plans = session.query(ProductionPlan).all()
        session.close()
        return plans
    
    def resolve_production_plans_by_status(self, info, status):
        session = get_session()
        plans = session.query(ProductionPlan).filter(ProductionPlan.status == status).all()
        session.close()
        return plans
    
    def resolve_capacity_plan(self, info, id):
        session = get_session()
        plan = session.query(CapacityPlan).filter(CapacityPlan.id == id).first()
        session.close()
        return plan
    
    def resolve_all_capacity_plans(self, info):
        session = get_session()
        plans = session.query(CapacityPlan).all()
        session.close()
        return plans
    
    def resolve_capacity_plans_by_date(self, info, date):
        session = get_session()
        plans = session.query(CapacityPlan).filter(
            and_(
                CapacityPlan.period_start <= date,
                CapacityPlan.period_end >= date
            )
        ).all()
        session.close()
        return plans

schema = graphene.Schema(query=Query, mutation=Mutation)
