import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from models import ProductionBatch, ProductionStep, StepMaterial, ProductDefinition, get_session
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
class ProductionBatchType(SQLAlchemyObjectType):
    class Meta:
        model = ProductionBatch
        interfaces = (relay.Node, )

class ProductionStepType(SQLAlchemyObjectType):
    class Meta:
        model = ProductionStep
        interfaces = (relay.Node, )

class StepMaterialType(SQLAlchemyObjectType):
    class Meta:
        model = StepMaterial
        interfaces = (relay.Node, )

class ProductDefinitionType(SQLAlchemyObjectType):
    class Meta:
        model = ProductDefinition
        interfaces = (relay.Node, )

# Input types for mutations
class ProductionBatchInput(graphene.InputObjectType):
    order_id = graphene.String()
    product_id = graphene.Int(required=True)
    quantity = graphene.Int(required=True)
    priority = graphene.Int()
    production_plan_id = graphene.Int()
    scheduled_start = graphene.DateTime()
    scheduled_end = graphene.DateTime()

class ProductionStepInput(graphene.InputObjectType):
    batch_id = graphene.Int(required=True)
    step_number = graphene.Int(required=True)
    name = graphene.String(required=True)
    machine_type = graphene.String()
    status = graphene.String()
    duration_minutes = graphene.Int()
    start_time = graphene.DateTime()
    end_time = graphene.DateTime()
    machine_queue_id = graphene.Int()
    notes = graphene.String()

class StepMaterialInput(graphene.InputObjectType):
    step_id = graphene.Int(required=True)
    material_id = graphene.Int(required=True)
    quantity_required = graphene.Float(required=True)
    is_consumed = graphene.Boolean()

class ProductDefinitionInput(graphene.InputObjectType):
    product_id = graphene.Int(required=True)
    name = graphene.String(required=True)
    description = graphene.String()
    production_workflow = graphene.JSONString()
    standard_batch_size = graphene.Int()
    is_active = graphene.Boolean()

# Helper functions for interacting with other services
def get_production_plan(plan_id):
    """Get production plan details from Production Planning Service"""
    try:
        query = """
        query($id: Int!) {
            productionPlan(id: $id) {
                id
                name
                startDate
                endDate
                status
            }
        }
        """
        variables = {"id": plan_id}
        
        # Make request to Production Planning Service
        response = requests.post(
            GRAPHQL_ENDPOINTS["production_planning"],
            json={"query": query, "variables": variables}
        )
        
        data = response.json()
        if 'data' in data and 'productionPlan' in data['data']:
            return data['data']['productionPlan']
        return None
    except Exception as e:
        print(f"Error fetching production plan: {e}")
        return None

def add_to_machine_queue(step_id, machine_type, start_time, duration_minutes):
    """Add a production step to the machine queue"""
    try:
        mutation = """
        mutation($input: AddToQueueInput!) {
            addToQueue(input: $input) {
                machineQueueItem {
                    id
                }
                success
                message
            }
        }
        """
        variables = {
            "input": {
                "productionStepId": step_id,
                "machineType": machine_type,
                "startTime": start_time.isoformat() if start_time else None,
                "durationMinutes": duration_minutes
            }
        }
        
        # Make request to Machine Queue Service
        response = requests.post(
            GRAPHQL_ENDPOINTS["machine_queue"],
            json={"query": mutation, "variables": variables}
        )
        
        data = response.json()
        if 'data' in data and 'addToQueue' in data['data']:
            return data['data']['addToQueue']
        return None
    except Exception as e:
        print(f"Error adding to machine queue: {e}")
        return None

def update_material_inventory(material_id, quantity, transaction_type, reference):
    """Update material inventory when materials are consumed"""
    try:
        mutation = """
        mutation($input: MaterialTransactionInput!) {
            createMaterialTransaction(input: $input) {
                materialTransaction {
                    id
                }
                material {
                    id
                    quantity
                }
            }
        }
        """
        variables = {
            "input": {
                "materialId": material_id,
                "transactionType": transaction_type,
                "quantity": quantity,
                "reference": reference
            }
        }
        
        # Make request to Material Inventory Service
        response = requests.post(
            GRAPHQL_ENDPOINTS["material_inventory"],
            json={"query": mutation, "variables": variables}
        )
        
        data = response.json()
        if 'data' in data and 'createMaterialTransaction' in data['data']:
            return data['data']['createMaterialTransaction']
        return None
    except Exception as e:
        print(f"Error updating material inventory: {e}")
        return None

def send_production_feedback(batch_id, status, completion_percentage, quality_data=None):
    """Send production status updates to Production Feedback Service"""
    try:
        mutation = """
        mutation($input: ProductionFeedbackInput!) {
            createProductionFeedback(input: $input) {
                productionFeedback {
                    id
                }
                success
                message
            }
        }
        """
        variables = {
            "input": {
                "batchId": batch_id,
                "status": status,
                "completionPercentage": completion_percentage,
                "qualityData": json.dumps(quality_data) if quality_data else None
            }
        }
        
        # Make request to Production Feedback Service
        response = requests.post(
            GRAPHQL_ENDPOINTS["production_feedback"],
            json={"query": mutation, "variables": variables}
        )
        
        data = response.json()
        if 'data' in data and 'createProductionFeedback' in data['data']:
            return data['data']['createProductionFeedback']
        return None
    except Exception as e:
        print(f"Error sending production feedback: {e}")
        return None

# Mutations
class CreateProductionBatch(graphene.Mutation):
    class Arguments:
        input = ProductionBatchInput(required=True)
    
    production_batch = graphene.Field(lambda: ProductionBatchType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        session = get_session()
        
        # Generate batch number
        batch_number = f"BATCH-{datetime.datetime.now().strftime('%Y%m%d')}-{input.product_id}-{input.quantity}"
        
        # Check production plan if provided
        if input.production_plan_id:
            plan = get_production_plan(input.production_plan_id)
            if not plan:
                return CreateProductionBatch(
                    production_batch=None,
                    success=False,
                    message=f"Production plan with ID {input.production_plan_id} not found"
                )
        
        # Create production batch
        batch = ProductionBatch(
            batch_number=batch_number,
            order_id=input.order_id,
            product_id=input.product_id,
            quantity=input.quantity,
            priority=input.priority or 1,
            status='pending',
            production_plan_id=input.production_plan_id,
            scheduled_start=input.scheduled_start,
            scheduled_end=input.scheduled_end
        )
        
        session.add(batch)
        session.commit()
        session.refresh(batch)
        
        # Get product definition to create steps
        product_def = session.query(ProductDefinition).filter(ProductDefinition.product_id == input.product_id).first()
        
        if product_def and product_def.production_workflow:
            try:
                workflow = json.loads(product_def.production_workflow) if isinstance(product_def.production_workflow, str) else product_def.production_workflow
                
                # Create production steps based on workflow
                for step_index, step_def in enumerate(workflow.get('steps', [])):
                    step = ProductionStep(
                        batch_id=batch.id,
                        step_number=step_index + 1,
                        name=step_def.get('name', f"Step {step_index + 1}"),
                        machine_type=step_def.get('machine_type'),
                        status='pending',
                        duration_minutes=step_def.get('duration_minutes')
                    )
                    session.add(step)
                    session.flush()  # Get step ID
                    
                    # Add materials for the step
                    for material in step_def.get('materials', []):
                        step_material = StepMaterial(
                            step_id=step.id,
                            material_id=material.get('material_id'),
                            quantity_required=material.get('quantity') * input.quantity
                        )
                        session.add(step_material)
                
                session.commit()
            except Exception as e:
                print(f"Error creating production steps: {e}")
        
        session.close()
        
        # Send initial feedback to Production Feedback Service
        send_production_feedback(batch.id, 'pending', 0)
        
        return CreateProductionBatch(
            production_batch=batch,
            success=True,
            message="Production batch created successfully"
        )

class UpdateProductionBatch(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = ProductionBatchInput(required=True)
    
    production_batch = graphene.Field(lambda: ProductionBatchType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, id, input):
        session = get_session()
        batch = session.query(ProductionBatch).filter(ProductionBatch.id == id).first()
        
        if not batch:
            return UpdateProductionBatch(
                production_batch=None,
                success=False,
                message=f"Production batch with ID {id} not found"
            )
        
        # Update batch fields
        batch.order_id = input.order_id or batch.order_id
        batch.product_id = input.product_id
        batch.quantity = input.quantity
        batch.priority = input.priority or batch.priority
        batch.production_plan_id = input.production_plan_id
        batch.scheduled_start = input.scheduled_start or batch.scheduled_start
        batch.scheduled_end = input.scheduled_end or batch.scheduled_end
        
        session.commit()
        session.refresh(batch)
        session.close()
        
        return UpdateProductionBatch(
            production_batch=batch,
            success=True,
            message="Production batch updated successfully"
        )

class StartProductionBatch(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
    
    production_batch = graphene.Field(lambda: ProductionBatchType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, id):
        session = get_session()
        batch = session.query(ProductionBatch).filter(ProductionBatch.id == id).first()
        
        if not batch:
            return StartProductionBatch(
                production_batch=None,
                success=False,
                message=f"Production batch with ID {id} not found"
            )
        
        # Check if batch can be started
        if batch.status != 'pending':
            return StartProductionBatch(
                production_batch=None,
                success=False,
                message=f"Cannot start batch with status '{batch.status}'"
            )
        
        # Start the batch
        batch.status = 'in_progress'
        batch.actual_start = datetime.datetime.utcnow()
        
        # Get first step and add to machine queue
        first_step = session.query(ProductionStep).filter(
            ProductionStep.batch_id == id,
            ProductionStep.step_number == 1
        ).first()
        
        if first_step:
            first_step.status = 'in_progress'
            first_step.start_time = datetime.datetime.utcnow()
            
            # Add to machine queue
            queue_result = add_to_machine_queue(
                first_step.id,
                first_step.machine_type,
                first_step.start_time,
                first_step.duration_minutes
            )
            
            if queue_result and queue_result.get('success'):
                first_step.machine_queue_id = queue_result.get('machineQueueItem', {}).get('id')
            
            # Reserve materials
            step_materials = session.query(StepMaterial).filter(StepMaterial.step_id == first_step.id).all()
            for material in step_materials:
                update_material_inventory(
                    material.material_id,
                    material.quantity_required,
                    'out',
                    f"Batch {batch.batch_number}, Step {first_step.step_number}"
                )
                material.is_consumed = True
        
        session.commit()
        session.refresh(batch)
        session.close()
        
        # Send update to Production Feedback Service
        send_production_feedback(batch.id, 'in_progress', 0)
        
        return StartProductionBatch(
            production_batch=batch,
            success=True,
            message="Production batch started successfully"
        )

class CompleteProductionStep(graphene.Mutation):
    class Arguments:
        step_id = graphene.Int(required=True)
        quality_data = graphene.JSONString()
    
    production_step = graphene.Field(lambda: ProductionStepType)
    next_step = graphene.Field(lambda: ProductionStepType)
    batch_completed = graphene.Boolean()
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, step_id, quality_data=None):
        session = get_session()
        step = session.query(ProductionStep).filter(ProductionStep.id == step_id).first()
        
        if not step:
            return CompleteProductionStep(
                production_step=None,
                next_step=None,
                batch_completed=False,
                success=False,
                message=f"Production step with ID {step_id} not found"
            )
        
        # Complete the current step
        step.status = 'completed'
        step.end_time = datetime.datetime.utcnow()
        
        # Get batch
        batch = session.query(ProductionBatch).filter(ProductionBatch.id == step.batch_id).first()
        
        # Get total steps count and completed steps
        total_steps = session.query(ProductionStep).filter(ProductionStep.batch_id == step.batch_id).count()
        completed_steps = session.query(ProductionStep).filter(
            ProductionStep.batch_id == step.batch_id,
            ProductionStep.status == 'completed'
        ).count() + 1  # +1 for the current step
        
        completion_percentage = (completed_steps / total_steps) * 100 if total_steps > 0 else 0
        
        # Check if this is the last step
        batch_completed = False
        next_step = None
        
        if completed_steps >= total_steps:
            # Complete the batch
            batch.status = 'completed'
            batch.actual_end = datetime.datetime.utcnow()
            batch_completed = True
        else:
            # Get the next step
            next_step = session.query(ProductionStep).filter(
                ProductionStep.batch_id == step.batch_id,
                ProductionStep.step_number == step.step_number + 1
            ).first()
            
            if next_step:
                next_step.status = 'in_progress'
                next_step.start_time = datetime.datetime.utcnow()
                
                # Add to machine queue
                queue_result = add_to_machine_queue(
                    next_step.id,
                    next_step.machine_type,
                    next_step.start_time,
                    next_step.duration_minutes
                )
                
                if queue_result and queue_result.get('success'):
                    next_step.machine_queue_id = queue_result.get('machineQueueItem', {}).get('id')
                
                # Reserve materials
                step_materials = session.query(StepMaterial).filter(StepMaterial.step_id == next_step.id).all()
                for material in step_materials:
                    update_material_inventory(
                        material.material_id,
                        material.quantity_required,
                        'out',
                        f"Batch {batch.batch_number}, Step {next_step.step_number}"
                    )
                    material.is_consumed = True
        
        session.commit()
        session.refresh(step)
        if next_step:
            session.refresh(next_step)
        session.close()
        
        # Send update to Production Feedback Service
        send_production_feedback(
            batch.id,
            batch.status,
            completion_percentage,
            json.loads(quality_data) if quality_data else None
        )
        
        return CompleteProductionStep(
            production_step=step,
            next_step=next_step,
            batch_completed=batch_completed,
            success=True,
            message="Production step completed successfully"
        )

class CreateProductDefinition(graphene.Mutation):
    class Arguments:
        input = ProductDefinitionInput(required=True)
    
    product_definition = graphene.Field(lambda: ProductDefinitionType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        session = get_session()
        
        # Check if product definition already exists
        existing = session.query(ProductDefinition).filter(ProductDefinition.product_id == input.product_id).first()
        if existing:
            return CreateProductDefinition(
                product_definition=None,
                success=False,
                message=f"Product definition for product ID {input.product_id} already exists"
            )
        
        # Create product definition
        product_def = ProductDefinition(
            product_id=input.product_id,
            name=input.name,
            description=input.description,
            production_workflow=input.production_workflow,
            standard_batch_size=input.standard_batch_size or 1,
            is_active=input.is_active if input.is_active is not None else True
        )
        
        session.add(product_def)
        session.commit()
        session.refresh(product_def)
        session.close()
        
        return CreateProductDefinition(
            product_definition=product_def,
            success=True,
            message="Product definition created successfully"
        )

class UpdateProductDefinition(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = ProductDefinitionInput(required=True)
    
    product_definition = graphene.Field(lambda: ProductDefinitionType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, id, input):
        session = get_session()
        product_def = session.query(ProductDefinition).filter(ProductDefinition.id == id).first()
        
        if not product_def:
            return UpdateProductDefinition(
                product_definition=None,
                success=False,
                message=f"Product definition with ID {id} not found"
            )
        
        # Update product definition
        product_def.product_id = input.product_id
        product_def.name = input.name
        product_def.description = input.description or product_def.description
        product_def.production_workflow = input.production_workflow or product_def.production_workflow
        product_def.standard_batch_size = input.standard_batch_size or product_def.standard_batch_size
        product_def.is_active = input.is_active if input.is_active is not None else product_def.is_active
        
        session.commit()
        session.refresh(product_def)
        session.close()
        
        return UpdateProductDefinition(
            product_definition=product_def,
            success=True,
            message="Product definition updated successfully"
        )

class Mutation(graphene.ObjectType):
    create_production_batch = CreateProductionBatch.Field()
    update_production_batch = UpdateProductionBatch.Field()
    start_production_batch = StartProductionBatch.Field()
    complete_production_step = CompleteProductionStep.Field()
    
    create_product_definition = CreateProductDefinition.Field()
    update_product_definition = UpdateProductDefinition.Field()

# Queries
class Query(graphene.ObjectType):
    node = relay.Node.Field()
    
    # Production batch queries
    production_batch = graphene.Field(ProductionBatchType, id=graphene.Int())
    all_production_batches = graphene.List(ProductionBatchType)
    production_batches_by_status = graphene.List(ProductionBatchType, status=graphene.String())
    production_batches_by_product = graphene.List(ProductionBatchType, product_id=graphene.Int())
    
    # Production step queries
    production_step = graphene.Field(ProductionStepType, id=graphene.Int())
    production_steps_by_batch = graphene.List(ProductionStepType, batch_id=graphene.Int())
    
    # Product definition queries
    product_definition = graphene.Field(ProductDefinitionType, id=graphene.Int())
    product_definition_by_product = graphene.Field(ProductDefinitionType, product_id=graphene.Int())
    all_product_definitions = graphene.List(ProductDefinitionType)
    active_product_definitions = graphene.List(ProductDefinitionType)
    
    def resolve_production_batch(self, info, id):
        session = get_session()
        batch = session.query(ProductionBatch).filter(ProductionBatch.id == id).first()
        session.close()
        return batch
    
    def resolve_all_production_batches(self, info):
        session = get_session()
        batches = session.query(ProductionBatch).all()
        session.close()
        return batches
    
    def resolve_production_batches_by_status(self, info, status):
        session = get_session()
        batches = session.query(ProductionBatch).filter(ProductionBatch.status == status).all()
        session.close()
        return batches
    
    def resolve_production_batches_by_product(self, info, product_id):
        session = get_session()
        batches = session.query(ProductionBatch).filter(ProductionBatch.product_id == product_id).all()
        session.close()
        return batches
    
    def resolve_production_step(self, info, id):
        session = get_session()
        step = session.query(ProductionStep).filter(ProductionStep.id == id).first()
        session.close()
        return step
    
    def resolve_production_steps_by_batch(self, info, batch_id):
        session = get_session()
        steps = session.query(ProductionStep).filter(ProductionStep.batch_id == batch_id).order_by(ProductionStep.step_number).all()
        session.close()
        return steps
    
    def resolve_product_definition(self, info, id):
        session = get_session()
        product_def = session.query(ProductDefinition).filter(ProductDefinition.id == id).first()
        session.close()
        return product_def
    
    def resolve_product_definition_by_product(self, info, product_id):
        session = get_session()
        product_def = session.query(ProductDefinition).filter(ProductDefinition.product_id == product_id).first()
        session.close()
        return product_def
    
    def resolve_all_product_definitions(self, info):
        session = get_session()
        product_defs = session.query(ProductDefinition).all()
        session.close()
        return product_defs
    
    def resolve_active_product_definitions(self, info):
        session = get_session()
        product_defs = session.query(ProductDefinition).filter(ProductDefinition.is_active == True).all()
        session.close()
        return product_defs

schema = graphene.Schema(query=Query, mutation=Mutation)
