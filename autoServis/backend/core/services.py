from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import Order, Part, OrderPart, OrderService, StockMovement, Payment, OrderStatusHistory

ALLOWED_TRANSITIONS = {'NEW': {'DIAGNOSTICS', 'CANCELLED'}, 'DIAGNOSTICS': {'ASSIGNED', 'CANCELLED'}, 'ASSIGNED': {'IN_PROGRESS', 'CANCELLED'}, 'IN_PROGRESS': {'COMPLETED', 'CANCELLED'}, 'COMPLETED': {'PAID', 'CANCELLED'}, 'PAID': set(), 'CANCELLED': set()}

def staff(user):
    if user.role not in ('admin', 'manager'):
        raise PermissionDenied('Admin yoki manager ruxsati kerak.')

def editable(order):
    if order.status in ('PAID', 'CANCELLED', 'COMPLETED'):
        raise ValidationError('Yakunlangan buyurtmani tahrirlab bo‘lmaydi.')

def quantity(value):
    try:
        number = int(str(value))
    except (ValueError, TypeError):
        raise ValidationError('Miqdor butun son bo‘lishi kerak.')
    if number < 1:
        raise ValidationError('Miqdor musbat bo‘lishi kerak.')
    return number

def recalculate_total(order):
    order.total_price = sum((x.price * x.quantity for x in order.services.all()), Decimal(0)) + sum((x.price * x.quantity for x in order.parts.all()), Decimal(0))
    order.save(update_fields=['total_price', 'updated_at'])

def change_status(order, new_status, user, comment=''):
    if new_status not in ALLOWED_TRANSITIONS[order.status]:
        raise ValidationError(f'{order.status} → {new_status}: o‘tish mumkin emas.')
    if user.role == 'mechanic' and order.mechanic_id == user.id and new_status in ('IN_PROGRESS', 'COMPLETED'):
        pass
    else:
        staff(user)
    if new_status == 'ASSIGNED' and not order.mechanic_id:
        raise ValidationError('Usta tanlanmagan.')
    if new_status == 'PAID':
        paid = order.payments.aggregate(total=Sum('amount'))['total'] or Decimal(0)
        if paid != order.total_price:
            raise ValidationError('To‘lov to‘liq emas.')
    if new_status == 'CANCELLED' and order.payments.exists():
        raise ValidationError('To‘lov mavjud: avval qaytarish jarayonini hal qiling.')
    old = order.status
    order.status = new_status
    if new_status in ('PAID', 'CANCELLED'):
        order.closed_at = timezone.now()
    order.save()
    OrderStatusHistory.objects.create(order=order, old_status=old, new_status=new_status, changed_by=user, comment=comment)

@transaction.atomic
def add_part(order_id, part_id, count, user):
    order = Order.objects.select_for_update().get(pk=order_id)
    editable(order)
    if order.status != 'IN_PROGRESS':
        raise ValidationError('Qismlar faqat ta’mirlash paytida qo‘shiladi.')
    staff(user)
    count = quantity(count)
    part = Part.objects.select_for_update().filter(pk=quantity(part_id)).first()
    if not part:
        raise ValidationError('Qism topilmadi.')
    if part.quantity < count:
        raise ValidationError('Omborda qism yetarli emas.')
    part.quantity -= count
    part.save(update_fields=['quantity'])
    OrderPart.objects.create(order=order, part=part, price=part.price, quantity=count)
    StockMovement.objects.create(part=part, order=order, change=-count, reason='usage', created_by=user)
    recalculate_total(order)
    return order

@transaction.atomic
def accept_payment(order_id, amount, method, user):
    staff(user)
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status != 'COMPLETED':
        raise ValidationError('Faqat tugallangan buyurtmaga to‘lov mumkin.')
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError):
        raise ValidationError('Summa noto‘g‘ri.')
    paid = order.payments.aggregate(total=Sum('amount'))['total'] or Decimal(0)
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2 or amount + paid > order.total_price:
        raise ValidationError('Summa musbat, ikki xona aniqlikda va qarzdan oshmasligi kerak.')
    if method not in ('cash', 'card', 'transfer'):
        raise ValidationError('To‘lov usuli noto‘g‘ri.')
    Payment.objects.create(order=order, amount=amount, method=method, received_by=user)
    if paid + amount == order.total_price:
        change_status(order, 'PAID', user)
    return order
