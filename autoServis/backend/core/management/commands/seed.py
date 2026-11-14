from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import User, Car, Service, Part, Order, OrderService, StockMovement, OrderStatusHistory
from core.services import change_status, recalculate_total, add_part, accept_payment

class Command(BaseCommand):
    help = 'Create local demo users and orders. Never run on a public production database.'
    @transaction.atomic
    def handle(self, *args, **options):
        users = {}
        for username, role, name in [('admin','admin','Aziz Karimov'),('manager','manager','Dilshod Rahimov'),('mechanic','mechanic','Javohir Alimov'),('client','client','Sardor Tursunov'),('client2','client','Madina Akbarova')]:
            user, created = User.objects.get_or_create(username=username, defaults={'role':role,'full_name':name,'phone':'+998 90 123 45 67'})
            if created:
                user.set_password('DemoPass123!');user.save()
            users[username]=user
        services=[]
        for name, price, hours in [('Moy almashtirish',120000,1),('Kompyuter diagnostikasi',180000,1),('Tormoz tizimini ta’mirlash',350000,3),('G‘ildiraklarni muvozanatlash',160000,2),('Dvigatel diagnostikasi',250000,2)]:
            service,_=Service.objects.get_or_create(name=name, defaults={'price':price,'estimated_hours':hours});services.append(service)
        parts=[]
        for name, sku, price, count, unit in [('Motor moyi 5W-30','OIL-530',85000,24,'litr'),('Moy filtri','FLT-001',65000,4,'dona'),('Tormoz kolodkasi','BRK-012',220000,3,'to‘plam'),('Havo filtri','AIR-003',90000,16,'dona')]:
            part,created=Part.objects.get_or_create(sku=sku,defaults={'name':name,'price':price,'quantity':count,'unit':unit})
            if created:StockMovement.objects.create(part=part,change=count,reason='purchase',created_by=users['admin'])
            parts.append(part)
        if not Order.objects.exists():
            for i,(brand,model,plate,target) in enumerate([('Chevrolet','Malibu','01 A 777 AA','PAID'),('Kia','K5','01 B 205 BB','IN_PROGRESS'),('Chevrolet','Cobalt','10 C 310 CC','DIAGNOSTICS'),('Hyundai','Sonata','01 D 450 DD','COMPLETED'),('BYD','Song Plus','01 E 550 EE','NEW'),('Chevrolet','Tracker','30 F 120 FF','ASSIGNED')]):
                client=users['client' if i%2==0 else 'client2']
                car,_=Car.objects.get_or_create(plate_number=plate,defaults={'owner':client,'brand':brand,'model':model,'year':2022+i%3,'mileage':12000+i*15000})
                order=Order.objects.create(client=client,car=car,manager=users['manager'],problem_description=['Moy va filtrlarni almashtirish.','Tormozdan shovqin kelmoqda.','Dvigatel indikatori yondi.'][i%3])
                OrderStatusHistory.objects.create(order=order,new_status='NEW',changed_by=users['manager'])
                if target=='NEW':continue
                order.diagnosis_notes='Dastlabki tekshiruv o‘tkazildi. Kerakli xizmatlar belgilandi.'
                change_status(order,'DIAGNOSTICS',users['manager'])
                OrderService.objects.create(order=order,service=services[i%len(services)],price=services[i%len(services)].price,quantity=1)
                recalculate_total(order)
                if target=='DIAGNOSTICS':continue
                order.mechanic=users['mechanic'];change_status(order,'ASSIGNED',users['manager'])
                if target=='ASSIGNED':continue
                change_status(order,'IN_PROGRESS',users['mechanic'])
                order=add_part(order.id,parts[0].id,1,users['manager'])
                if target=='IN_PROGRESS':continue
                change_status(order,'COMPLETED',users['mechanic'])
                if target=='PAID':accept_payment(order.id,order.total_price,'card',users['manager'])
        self.stdout.write(self.style.SUCCESS('Demo ready: admin / manager / mechanic / client / client2 — DemoPass123!'))
