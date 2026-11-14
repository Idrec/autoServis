from django.test import TestCase
from rest_framework.test import APIClient
from .models import User, Car, Part, Service, Order, OrderService, PartRequest, StockMovement, AuditEvent

class RoleRequirementsTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.users = {r: User.objects.create_user(username=r, role=r, password='StrongDemo123!') for r in ['admin', 'manager', 'mechanic', 'client']}
        self.other_mechanic = User.objects.create_user(username='second_mechanic', role='mechanic')
        self.other_client = User.objects.create_user(username='second_client', role='client')
        self.car = Car.objects.create(owner=self.users['client'], brand='Kia', model='K5', year=2024, plate_number='TEST01')
        self.part = Part.objects.create(name='Filtr', sku='FILTR', price=50000, quantity=5)
        self.service = Service.objects.create(name='Diagnostika', price=100000)
        self.order = Order.objects.create(client=self.users['client'], car=self.car, manager=self.users['manager'], mechanic=self.users['mechanic'], status='IN_PROGRESS', problem_description='Test')
        OrderService.objects.create(order=self.order, service=self.service, price=self.service.price, quantity=1)
        from .services import recalculate_total
        recalculate_total(self.order)
    def as_role(self, role):
        self.api.force_authenticate(self.users[role])
    def order_post(self, action, data=None):
        return self.api.post(f'/api/orders/{self.order.pk}/{action}/', data or {}, format='json')

    def test_manager_customer_crud_cannot_manage_staff_or_roles(self):
        self.as_role('manager')
        customer = self.api.post('/api/users/', {'username': 'customer', 'password': 'StrongDemo123!', 'full_name': 'Mijoz'})
        self.assertEqual(customer.status_code, 201, customer.data)
        self.assertEqual(customer.data['role'], 'client')
        url = f"/api/users/{customer.data['id']}/"
        self.assertEqual(self.api.patch(url, {'full_name': 'Yangilangan'}).status_code, 200)
        for data in [{'role': 'admin'}, {'is_active': False}, {'password': 'StrongDemo123!', 'role': 'mechanic'}]:
            self.assertEqual(self.api.patch(url, data).status_code, 400)
        self.assertEqual(self.api.post('/api/users/', {'username': 'bad', 'password': 'StrongDemo123!', 'role': 'admin'}).status_code, 400)
        self.assertEqual(self.api.patch(f"/api/users/{self.users['mechanic'].pk}/", {'full_name': 'Bad'}).status_code, 403)
        self.assertEqual(self.api.delete(url).status_code, 403)

    def test_admin_block_role_and_audit(self):
        self.as_role('admin')
        uid = self.other_client.pk
        self.assertEqual(self.api.patch(f'/api/users/{uid}/', {'is_active': False}).status_code, 200)
        self.other_client.refresh_from_db()
        self.assertFalse(self.other_client.is_active)
        self.assertEqual(self.api.patch(f'/api/users/{uid}/', {'is_active': True, 'role': 'manager'}).status_code, 200)
        events = self.api.get('/api/audit/?entity=User').data['results']
        self.assertTrue(any(e['actor'] == self.users['admin'].pk and e['entity_id'] == uid for e in events))
        self.as_role('manager')
        self.assertEqual(self.api.get('/api/audit/').status_code, 403)

    def test_admin_can_create_every_user_role(self):
        self.as_role('admin')
        for role in ['admin', 'manager', 'mechanic', 'client']:
            response = self.api.post('/api/users/', {
                'username': f'created_{role}', 'password': 'StrongDemo123!',
                'full_name': f'New {role}', 'role': role, 'is_active': True,
            }, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            created = User.objects.get(pk=response.data['id'])
            self.assertEqual(created.role, role)
            self.assertTrue(created.check_password('StrongDemo123!'))
            self.api.force_authenticate(None)
            login = self.api.post('/api/auth/login/', {'username': created.username, 'password': 'StrongDemo123!'})
            self.assertEqual(login.status_code, 200, login.data)
            self.as_role('admin')

    def test_manager_assigns_new_order_with_diagnosis_and_mechanic_sees_it(self):
        self.order.status = 'NEW'
        self.order.mechanic = None
        self.order.save()
        self.as_role('manager')
        self.assertEqual(self.order_post('assign', {'mechanic': self.users['mechanic'].pk}).status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'NEW')
        self.assertEqual(self.order.history.count(), 0)
        self.assertEqual(self.order_post('assign', {'mechanic': self.users['client'].pk, 'diagnosis_notes': 'Test'}).status_code, 404)
        result = self.order_post('assign', {'mechanic': self.users['mechanic'].pk, 'diagnosis_notes': 'Filtrni almashtirish kerak'})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['status'], 'ASSIGNED')
        self.assertEqual(result.data['mechanic'], self.users['mechanic'].pk)
        self.assertEqual(list(self.order.history.order_by('pk').values_list('new_status', flat=True)), ['DIAGNOSTICS', 'ASSIGNED'])
        self.as_role('mechanic')
        self.assertEqual(self.api.get(f'/api/orders/{self.order.pk}/').status_code, 200)
        self.assertEqual(self.order_post('start').status_code, 200)

    def test_client_request_accept_is_atomic_and_scoped(self):
        self.as_role('client')
        response = self.api.post('/api/repair-requests/', {'car': self.car.pk, 'description': 'Moy almashtirish'})
        self.assertEqual(response.status_code, 201, response.data)
        rid = response.data['id']
        self.api.force_authenticate(self.other_client)
        self.assertEqual(self.api.get(f'/api/repair-requests/{rid}/').status_code, 404)
        self.assertEqual(self.api.post('/api/repair-requests/', {'car': self.car.pk, 'description': 'Bad'}).status_code, 400)
        self.as_role('client')
        self.assertEqual(self.api.post(f'/api/repair-requests/{rid}/accept/').status_code, 403)
        self.as_role('manager')
        accepted = self.api.post(f'/api/repair-requests/{rid}/accept/', {'response_note': 'Kelib keting'})
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.data['status'], 'ACCEPTED')
        order = Order.objects.get(pk=accepted.data['order'])
        self.assertEqual(order.client_id, self.users['client'].pk)
        self.assertEqual(order.history.count(), 1)
        self.assertEqual(self.api.post(f'/api/repair-requests/{rid}/accept/').status_code, 400)

    def test_mechanic_request_approval_once_and_stock_permissions(self):
        self.as_role('mechanic')
        self.assertEqual(self.order_post('parts', {'part': self.part.pk, 'quantity': 1}).status_code, 403)
        self.assertEqual(self.api.post(f'/api/parts/{self.part.pk}/restock/', {'quantity': 10}).status_code, 403)
        created = self.order_post('part-requests', {'part': self.part.pk, 'quantity': 2, 'note': 'Almashtirish uchun'})
        self.assertEqual(created.status_code, 200, created.data)
        rid = created.data[0]['id']
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 5)
        self.assertEqual(self.order_post('complete').status_code, 400)
        self.assertEqual(self.api.post(f'/api/part-requests/{rid}/approve/').status_code, 403)
        self.api.force_authenticate(self.other_mechanic)
        self.assertEqual(self.api.get(f'/api/part-requests/{rid}/').status_code, 404)
        self.assertEqual(self.order_post('work-logs', {'comment': 'Bad'}).status_code, 404)
        self.as_role('manager')
        self.assertEqual(self.api.post(f'/api/part-requests/{rid}/approve/').status_code, 200)
        self.assertEqual(self.api.post(f'/api/part-requests/{rid}/approve/').status_code, 400)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 3)
        self.assertEqual(StockMovement.objects.filter(reason='usage').count(), 1)
        self.as_role('mechanic')
        self.assertEqual(self.api.delete(f'/api/orders/{self.order.pk}/parts/{self.order.parts.get().pk}/').status_code, 403)

    def test_request_shortage_and_cancellation_reject_pending(self):
        self.as_role('mechanic')
        self.order_post('part-requests', {'part': self.part.pk, 'quantity': 6})
        req = PartRequest.objects.get()
        self.as_role('manager')
        self.assertEqual(self.api.post(f'/api/part-requests/{req.pk}/approve/').status_code, 400)
        req.refresh_from_db(); self.assertEqual(req.status, 'PENDING')
        self.assertEqual(self.order_post('cancel').status_code, 200)
        req.refresh_from_db(); self.assertEqual(req.status, 'REJECTED')
        self.part.refresh_from_db(); self.assertEqual(self.part.quantity, 5)

    def test_work_logs_feedback_invoice_and_dashboard_scope(self):
        self.as_role('mechanic')
        created = self.order_post('work-logs', {'diagnosis': 'Filtr nosoz', 'additional_faults': 'Shovqin', 'comment': 'Tekshirildi', 'minutes': 45})
        self.assertEqual(created.status_code, 200, created.data)
        self.assertEqual(self.order_post('work-logs', {'minutes': -1}).status_code, 400)
        self.assertEqual(self.api.get('/api/dashboard/').data['work_minutes'], 45)
        self.assertEqual(self.order_post('complete').status_code, 200)
        self.assertEqual(self.api.get(f'/api/orders/{self.order.pk}/invoice/').status_code, 403)
        self.as_role('client')
        invoice = self.api.get(f'/api/orders/{self.order.pk}/invoice/')
        self.assertEqual(invoice.status_code, 200)
        self.assertEqual(str(invoice.data['balance']), '100000.00')
        self.assertEqual(self.order_post('feedback', {'rating': 6}).status_code, 400)
        self.assertEqual(self.order_post('feedback', {'rating': 5, 'comment': 'Yaxshi'}).status_code, 200)
        self.assertEqual(self.order_post('feedback', {'rating': 4}).status_code, 400)
        self.assertEqual(self.api.patch(f'/api/orders/{self.order.pk}/feedback/', {'rating': 4}).status_code, 200)
        dashboard = self.api.get('/api/dashboard/').data
        self.assertEqual(dashboard['total_orders'], 1)
        self.assertEqual(dashboard['awaiting_payment'], 1)
        self.api.force_authenticate(self.other_client)
        self.assertEqual(self.api.get('/api/dashboard/').data['total_orders'], 0)
        self.assertEqual(self.api.get(f'/api/orders/{self.order.pk}/invoice/').status_code, 404)
        self.as_role('manager')
        self.assertEqual(self.order_post('feedback', {'rating': 5}).status_code, 403)

    def test_mechanic_car_history_does_not_leak_other_work(self):
        Order.objects.create(client=self.users['client'], car=self.car, manager=self.users['manager'], mechanic=self.other_mechanic, problem_description='Private')
        self.as_role('mechanic')
        response = self.api.get(f'/api/cars/{self.car.pk}/history/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([o['id'] for o in response.data], [self.order.pk])

    def test_blocked_account_cannot_use_existing_token(self):
        token = self.api.post('/api/auth/login/', {'username': 'client', 'password': 'StrongDemo123!'}).data['access']
        self.as_role('admin')
        self.api.patch(f"/api/users/{self.users['client'].pk}/", {'is_active': False})
        self.api.force_authenticate(None)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.api.get('/api/auth/me/').status_code, 401)
        self.api.credentials()
        self.assertEqual(self.api.post('/api/auth/login/', {'username': 'client', 'password': 'StrongDemo123!'}).status_code, 401)

    def test_readonly_roles_cannot_add_work_or_financial_data(self):
        self.as_role('client')
        self.assertEqual(self.order_post('work-logs', {'comment': 'Bad'}).status_code, 403)
        self.assertEqual(self.order_post('part-requests', {'part': self.part.pk, 'quantity': 1}).status_code, 403)
        self.assertEqual(self.api.get('/api/reports/summary/').status_code, 403)
        self.as_role('mechanic')
        self.assertEqual(self.api.patch(f'/api/services/{self.service.pk}/', {'price': 1}).status_code, 403)
        self.assertEqual(self.order_post('pay', {'amount': 1, 'method': 'cash'}).status_code, 403)
        self.assertEqual(self.api.delete(f"/api/users/{self.users['client'].pk}/").status_code, 403)
        self.assertEqual(self.api.get('/api/reports/summary/').status_code, 403)
