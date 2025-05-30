import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from models import Material, Supplier, MaterialTransaction, get_session
from sqlalchemy import desc

# Define GraphQL types
class MaterialType(SQLAlchemyObjectType):
    class Meta:
        model = Material
        interfaces = (relay.Node, )

class SupplierType(SQLAlchemyObjectType):
    class Meta:
        model = Supplier
        interfaces = (relay.Node, )

class MaterialTransactionType(SQLAlchemyObjectType):
    class Meta:
        model = MaterialTransaction
        interfaces = (relay.Node, )

# Input types for mutations
class MaterialInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    description = graphene.String()
    sku = graphene.String(required=True)
    unit = graphene.String(required=True)
    quantity = graphene.Float(required=True)
    min_stock_level = graphene.Float()
    supplier_id = graphene.Int()
    cost_per_unit = graphene.Float()
    location = graphene.String()

class SupplierInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    contact_person = graphene.String()
    email = graphene.String()
    phone = graphene.String()
    address = graphene.String()
    active = graphene.Boolean()

class MaterialTransactionInput(graphene.InputObjectType):
    material_id = graphene.Int(required=True)
    transaction_type = graphene.String(required=True)
    quantity = graphene.Float(required=True)
    reference = graphene.String()
    notes = graphene.String()

# Mutations
class CreateMaterial(graphene.Mutation):
    class Arguments:
        input = MaterialInput(required=True)
    
    material = graphene.Field(lambda: MaterialType)
    
    def mutate(self, info, input):
        session = get_session()
        material = Material(
            name=input.name,
            description=input.description,
            sku=input.sku,
            unit=input.unit,
            quantity=input.quantity,
            min_stock_level=input.min_stock_level,
            supplier_id=input.supplier_id,
            cost_per_unit=input.cost_per_unit,
            location=input.location
        )
        session.add(material)
        session.commit()
        session.refresh(material)
        session.close()
        return CreateMaterial(material=material)

class UpdateMaterial(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = MaterialInput(required=True)
    
    material = graphene.Field(lambda: MaterialType)
    
    def mutate(self, info, id, input):
        session = get_session()
        material = session.query(Material).filter(Material.id == id).first()
        
        if material:
            material.name = input.name
            material.description = input.description
            material.sku = input.sku
            material.unit = input.unit
            material.quantity = input.quantity
            material.min_stock_level = input.min_stock_level
            material.supplier_id = input.supplier_id
            material.cost_per_unit = input.cost_per_unit
            material.location = input.location
            
            session.commit()
            session.refresh(material)
        
        session.close()
        return UpdateMaterial(material=material)

class DeleteMaterial(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    
    def mutate(self, info, id):
        session = get_session()
        material = session.query(Material).filter(Material.id == id).first()
        
        if material:
            session.delete(material)
            session.commit()
            success = True
        else:
            success = False
        
        session.close()
        return DeleteMaterial(success=success)

class CreateSupplier(graphene.Mutation):
    class Arguments:
        input = SupplierInput(required=True)
    
    supplier = graphene.Field(lambda: SupplierType)
    
    def mutate(self, info, input):
        session = get_session()
        supplier = Supplier(
            name=input.name,
            contact_person=input.contact_person,
            email=input.email,
            phone=input.phone,
            address=input.address,
            active=input.active if input.active is not None else True
        )
        session.add(supplier)
        session.commit()
        session.refresh(supplier)
        session.close()
        return CreateSupplier(supplier=supplier)

class UpdateSupplier(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = SupplierInput(required=True)
    
    supplier = graphene.Field(lambda: SupplierType)
    
    def mutate(self, info, id, input):
        session = get_session()
        supplier = session.query(Supplier).filter(Supplier.id == id).first()
        
        if supplier:
            supplier.name = input.name
            supplier.contact_person = input.contact_person
            supplier.email = input.email
            supplier.phone = input.phone
            supplier.address = input.address
            supplier.active = input.active if input.active is not None else supplier.active
            
            session.commit()
            session.refresh(supplier)
        
        session.close()
        return UpdateSupplier(supplier=supplier)

class DeleteSupplier(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    
    def mutate(self, info, id):
        session = get_session()
        supplier = session.query(Supplier).filter(Supplier.id == id).first()
        
        if supplier:
            session.delete(supplier)
            session.commit()
            success = True
        else:
            success = False
        
        session.close()
        return DeleteSupplier(success=success)

class CreateMaterialTransaction(graphene.Mutation):
    class Arguments:
        input = MaterialTransactionInput(required=True)
    
    material_transaction = graphene.Field(lambda: MaterialTransactionType)
    material = graphene.Field(lambda: MaterialType)
    
    def mutate(self, info, input):
        session = get_session()
        
        # Create transaction
        transaction = MaterialTransaction(
            material_id=input.material_id,
            transaction_type=input.transaction_type,
            quantity=input.quantity,
            reference=input.reference,
            notes=input.notes
        )
        session.add(transaction)
        
        # Update material quantity
        material = session.query(Material).filter(Material.id == input.material_id).first()
        if material:
            if input.transaction_type == 'in':
                material.quantity += input.quantity
            elif input.transaction_type == 'out':
                material.quantity -= input.quantity
            elif input.transaction_type == 'adjustment':
                material.quantity = input.quantity
        
        session.commit()
        session.refresh(transaction)
        if material:
            session.refresh(material)
        
        session.close()
        return CreateMaterialTransaction(material_transaction=transaction, material=material)

class Mutation(graphene.ObjectType):
    create_material = CreateMaterial.Field()
    update_material = UpdateMaterial.Field()
    delete_material = DeleteMaterial.Field()
    
    create_supplier = CreateSupplier.Field()
    update_supplier = UpdateSupplier.Field()
    delete_supplier = DeleteSupplier.Field()
    
    create_material_transaction = CreateMaterialTransaction.Field()

# Queries
class Query(graphene.ObjectType):
    node = relay.Node.Field()
    
    # Material queries
    material = graphene.Field(MaterialType, id=graphene.Int())
    all_materials = graphene.List(MaterialType)
    materials_by_supplier = graphene.List(MaterialType, supplier_id=graphene.Int())
    low_stock_materials = graphene.List(MaterialType)
    
    # Supplier queries
    supplier = graphene.Field(SupplierType, id=graphene.Int())
    all_suppliers = graphene.List(SupplierType)
    active_suppliers = graphene.List(SupplierType)
    
    # Transaction queries
    material_transaction = graphene.Field(MaterialTransactionType, id=graphene.Int())
    material_transactions = graphene.List(MaterialTransactionType, material_id=graphene.Int())
    recent_transactions = graphene.List(MaterialTransactionType, limit=graphene.Int())
    
    def resolve_material(self, info, id):
        session = get_session()
        material = session.query(Material).filter(Material.id == id).first()
        session.close()
        return material
    
    def resolve_all_materials(self, info):
        session = get_session()
        materials = session.query(Material).all()
        session.close()
        return materials
    
    def resolve_materials_by_supplier(self, info, supplier_id):
        session = get_session()
        materials = session.query(Material).filter(Material.supplier_id == supplier_id).all()
        session.close()
        return materials
    
    def resolve_low_stock_materials(self, info):
        session = get_session()
        materials = session.query(Material).filter(Material.quantity <= Material.min_stock_level).all()
        session.close()
        return materials
    
    def resolve_supplier(self, info, id):
        session = get_session()
        supplier = session.query(Supplier).filter(Supplier.id == id).first()
        session.close()
        return supplier
    
    def resolve_all_suppliers(self, info):
        session = get_session()
        suppliers = session.query(Supplier).all()
        session.close()
        return suppliers
    
    def resolve_active_suppliers(self, info):
        session = get_session()
        suppliers = session.query(Supplier).filter(Supplier.active == True).all()
        session.close()
        return suppliers
    
    def resolve_material_transaction(self, info, id):
        session = get_session()
        transaction = session.query(MaterialTransaction).filter(MaterialTransaction.id == id).first()
        session.close()
        return transaction
    
    def resolve_material_transactions(self, info, material_id):
        session = get_session()
        transactions = session.query(MaterialTransaction).filter(MaterialTransaction.material_id == material_id).all()
        session.close()
        return transactions
    
    def resolve_recent_transactions(self, info, limit=10):
        session = get_session()
        transactions = session.query(MaterialTransaction).order_by(desc(MaterialTransaction.created_at)).limit(limit).all()
        session.close()
        return transactions

schema = graphene.Schema(query=Query, mutation=Mutation)
