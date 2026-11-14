from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from .models import User, Car, Service, Part, Order, StockMovement, OrderPart

class WorkflowTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.manager = User.objects.create_user(username='manager',password='TestPass123!',role='manager')
        self.mechanic = User.objects.create_user(username='mechanic',password='TestPass123!',role='mechanic')
        self.client_user = User.objects.create_user(username='client',password='TestPass123!',role='client')
        self.other = User.objects.create_user(username='other',password='TestPass123!',role='client')
        self.car = Car.objects.create(owner=self.client_user,brand='Kia',model='K5',year=2023,plate_number='01 TEST')
        self.service = Service.objects.create(name='Diagnostika',price=100000)
        self.part = Part.objects.create(name='Filtr',sku='F1',price=50000,quantity=5)
        self.api.force_authenticate(self.manager)
        response=self.api.post('/api/orders/',{'client':self.client_user.id,'car':self.car.id,'problem_description':'Tekshirish'})
        self.assertEqual(response.status_code,201,response.data)
        self.order_id=response.data['id']
    def post(self, action, data=None):
        return self.api.post(f'/api/orders/{self.order_id}/{action}/',data or {},format='json')
    def use_part(self, data):
        self.api.force_authenticate(self.manager)
        response = self.post('parts', data)
        self.api.force_authenticate(self.mechanic)
        return response
    def progress(self):
        self.assertEqual(self.post('diagnose',{'diagnosis_notes':'Test'}).status_code,200)
        self.assertEqual(self.post('services',{'service':self.service.id,'quantity':2}).status_code,200)
        self.assertEqual(self.post('assign',{'mechanic':self.mechanic.id}).status_code,200)
        self.api.force_authenticate(self.mechanic)
        self.assertEqual(self.post('start').status_code,200)
    def test_full_workflow_snapshot_partial_pay_and_lock(self):
        self.progress()
        self.assertEqual(self.use_part({'part':self.part.id,'quantity':2}).status_code,200)
        self.part.refresh_from_db();self.assertEqual(self.part.quantity,3)
        self.part.price=90000;self.part.save()
        self.service.price=300000;self.service.save()
        self.assertEqual(self.post('complete').status_code,200)
        order=Order.objects.get(pk=self.order_id);self.assertEqual(order.total_price,Decimal(300000))
        self.assertEqual(self.post('pay',{'amount':300000,'method':'cash'}).status_code,403)
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.post('pay',{'amount':100000,'method':'cash'}).data['status'],'COMPLETED')
        self.assertEqual(self.post('pay',{'amount':200001,'method':'card'}).status_code,400)
        self.assertEqual(self.post('pay',{'amount':200000,'method':'card'}).data['status'],'PAID')
        self.assertEqual(self.post('services',{'service':self.service.id}).status_code,400)
        self.assertEqual(self.post('cancel').status_code,400)
        self.assertEqual(self.api.patch(f'/api/orders/{self.order_id}/',{'problem_description':'changed'}).status_code,400)
        self.assertIsNotNone(Order.objects.get(pk=self.order_id).closed_at)
    def test_stock_shortage_and_return(self):
        self.progress()
        self.assertEqual(self.use_part({'part':self.part.id,'quantity':6}).status_code,400)
        self.part.refresh_from_db();self.assertEqual(self.part.quantity,5)
        self.assertEqual(OrderPart.objects.count(),0)
        self.assertEqual(self.use_part({'part':self.part.id,'quantity':2}).status_code,200)
        item=OrderPart.objects.get()
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.api.delete(f'/api/orders/{self.order_id}/parts/{item.id}/').status_code,200)
        self.part.refresh_from_db();self.assertEqual(self.part.quantity,5)
        self.assertEqual(StockMovement.objects.filter(reason='return').count(),1)
        self.assertEqual(Order.objects.get(pk=self.order_id).total_price,200000)
    def test_permissions_isolation_and_invalid_transition(self):
        self.assertEqual(self.post('complete').status_code,400)
        for user in [self.other,self.mechanic]:
            self.api.force_authenticate(user)
            self.assertEqual(self.api.get(f'/api/orders/{self.order_id}/').status_code,404)
            self.assertEqual(self.api.get('/api/orders/').data['count'],0)
            self.assertEqual(self.api.get('/api/reports/summary/').status_code,403)
        self.api.force_authenticate(self.client_user)
        self.assertEqual(self.api.get(f'/api/orders/{self.order_id}/').status_code,200)
        self.assertEqual(self.post('diagnose').status_code,403)
        self.assertEqual(self.api.patch('/api/auth/me/',{'role':'admin'}).data['role'],'client')
    def test_inventory_writes_and_cancel_returns_stock_once(self):
        self.assertEqual(self.api.patch(f'/api/parts/{self.part.id}/',{'quantity':100}).status_code,400)
        self.assertEqual(self.api.post(f'/api/parts/{self.part.id}/restock/',{'quantity':3}).status_code,200)
        self.progress()
        self.assertEqual(self.use_part({'part':self.part.id,'quantity':2}).status_code,200)
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.post('cancel').status_code,200)
        self.part.refresh_from_db();self.assertEqual(self.part.quantity,8)
        self.assertEqual(self.post('cancel').status_code,400)
        self.part.refresh_from_db();self.assertEqual(self.part.quantity,8)
    def test_registration_cannot_escalate_and_jwt(self):
        self.api.force_authenticate(None)
        result=self.api.post('/api/auth/register/',{'username':'new','password':'StrongDemo123!','role':'admin','is_active':False})
        self.assertEqual(result.status_code,201,result.data)
        self.assertEqual(result.data['role'],'client')
        token=self.api.post('/api/auth/login/',{'username':'new','password':'StrongDemo123!'})
        self.assertEqual(token.status_code,200)
        self.assertEqual(self.api.post('/api/auth/refresh/',{'refresh':token.data['refresh']}).status_code,200)
    def test_car_owner_validation_and_client_write_boundary(self):
        self.assertEqual(self.api.post('/api/orders/',{'client':self.other.id,'car':self.car.id,'problem_description':'Bad'}).status_code,400)
        self.api.force_authenticate(self.client_user)
        self.assertEqual(self.api.post('/api/cars/',{'owner':self.other.id,'brand':'Kia','model':'K5','year':2023,'plate_number':'BAD'}).status_code,400)
        self.assertEqual(self.api.post('/api/services/',{'name':'Bad','price':10}).status_code,403)
    def test_docs_and_reports_render(self):
        for path in ['docs/', 'schema/', 'reports/summary/', 'reports/revenue/', 'reports/top-services/', 'reports/mechanics/', 'reports/low-stock/']:
            response = self.api.get('/api/' + path)
            self.assertEqual(response.status_code, 200, path)
