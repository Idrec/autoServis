from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        MANAGER = 'manager', 'Manager'
        MECHANIC = 'mechanic', 'Usta'
        CLIENT = 'client', 'Mijoz'
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CLIENT)
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)


class Car(models.Model):
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cars')
    brand = models.CharField(max_length=80)
    model = models.CharField(max_length=80)
    year = models.PositiveIntegerField()
    plate_number = models.CharField(max_length=20, unique=True)
    vin = models.CharField(max_length=30, blank=True)
    mileage = models.PositiveIntegerField(default=0)


class Service(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    is_active = models.BooleanField(default=True)


class Part(models.Model):
    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    min_quantity = models.PositiveIntegerField(default=5)
    unit = models.CharField(max_length=20, default='dona')


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'NEW', 'Yangi'
        DIAGNOSTICS = 'DIAGNOSTICS', 'Diagnostika'
        ASSIGNED = 'ASSIGNED', 'Biriktirilgan'
        IN_PROGRESS = 'IN_PROGRESS', 'Jarayonda'
        COMPLETED = 'COMPLETED', 'Tugallangan'
        PAID = 'PAID', 'To‘langan'
        CANCELLED = 'CANCELLED', 'Bekor qilingan'
    client = models.ForeignKey(User, on_delete=models.PROTECT, related_name='client_orders')
    car = models.ForeignKey(Car, on_delete=models.PROTECT, related_name='orders')
    mechanic = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='mechanic_orders')
    manager = models.ForeignKey(User, on_delete=models.PROTECT, related_name='manager_orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    problem_description = models.TextField()
    diagnosis_notes = models.TextField(blank=True)
    total_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-created_at']


class OrderService(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='services')
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name='service_quantity_positive')]


class OrderPart(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='parts')
    part = models.ForeignKey(Part, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField()
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name='part_quantity_positive')]


class StockMovement(models.Model):
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name='movements')
    order = models.ForeignKey(Order, null=True, on_delete=models.PROTECT)
    change = models.IntegerField()
    reason = models.CharField(max_length=20, choices=[(x, x) for x in ['purchase', 'usage', 'return', 'correction']])
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=10, choices=[('cash', 'Naqd'), ('card', 'Karta'), ('transfer', 'O‘tkazma')])
    paid_at = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(User, on_delete=models.PROTECT)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='history')
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    changed_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)


class RepairRequest(models.Model):
    client = models.ForeignKey(User, on_delete=models.PROTECT, related_name='repair_requests')
    car = models.ForeignKey(Car, on_delete=models.PROTECT)
    description = models.TextField()
    status = models.CharField(max_length=12, choices=[('PENDING', 'Kutilmoqda'), ('ACCEPTED', 'Qabul qilingan'), ('REJECTED', 'Rad etilgan')], default='PENDING')
    order = models.OneToOneField(Order, null=True, blank=True, on_delete=models.PROTECT)
    response_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name='reviewed_requests')
    class Meta:
        ordering = ['-created_at']


class PartRequest(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='part_requests')
    part = models.ForeignKey(Part, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='part_requests')
    note = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=[('PENDING', 'Kutilmoqda'), ('APPROVED', 'Tasdiqlangan'), ('REJECTED', 'Rad etilgan')], default='PENDING')
    reviewed_by = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name='reviewed_parts')
    reviewed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name='request_quantity_positive')]


class WorkLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='work_logs')
    mechanic = models.ForeignKey(User, on_delete=models.PROTECT)
    diagnosis = models.TextField(blank=True)
    additional_faults = models.TextField(blank=True)
    comment = models.TextField(blank=True)
    minutes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']


class Review(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='review')
    client = models.ForeignKey(User, on_delete=models.PROTECT)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name='review_rating_range')]


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    entity = models.CharField(max_length=80)
    entity_id = models.PositiveBigIntegerField()
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
