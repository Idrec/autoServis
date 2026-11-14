from decimal import Decimal
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Sum, Count, F, Q
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import *
from .serializers import *
from .services import staff, editable, quantity, change_status, recalculate_total, add_part, accept_payment
from .permissions import IsAdminOrManager, IsOrderParticipant

class SafeModelViewSet(viewsets.ModelViewSet):
    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError('Bu yozuv tarixda ishlatilgan, o‘chirib bo‘lmaydi.')

@extend_schema(request=RegisterSerializer, responses={201: UserSerializer})
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register(request):
    data = request.data.copy()
    data['role'] = 'client'
    data['is_active'] = True
    serializer = UserSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=201)

@extend_schema(methods=['GET'], responses=UserSerializer)
@extend_schema(methods=['PATCH'], request=ProfileSerializer, responses=UserSerializer)
@api_view(['GET', 'PATCH'])
def me(request):
    if request.method == 'PATCH':
        allowed = {k: v for k, v in request.data.items() if k in ('full_name', 'phone', 'email')}
        serializer = UserSerializer(request.user, data=allowed, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(UserSerializer(request.user).data)

@extend_schema(request=PasswordSerializer, responses={200: {'type': 'object', 'properties': {'detail': {'type': 'string'}}}})
@api_view(['POST'])
def change_password(request):
    if not request.user.check_password(request.data.get('old_password', '')):
        raise ValidationError('Eski parol noto‘g‘ri.')
    password = request.data.get('new_password', '')
    try:
        validate_password(password, request.user)
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages)
    request.user.set_password(password)
    request.user.save()
    return Response({'detail': 'Parol yangilandi.'})

class UserViewSet(SafeModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all().order_by('id')
    filterset_fields = ['role', 'is_active']
    search_fields = ['full_name', 'username', 'phone']
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.role != 'admin' and not (request.user.role == 'manager' and (request.method in permissions.SAFE_METHODS or self.action in ('create', 'update', 'partial_update'))):
            raise PermissionDenied()
    def get_serializer_class(self):
        if getattr(self.request.user, 'role', None) == 'manager' and self.request.method not in permissions.SAFE_METHODS:
            return CustomerSerializer
        return UserSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.exclude(role='admin') if self.request.user.role == 'manager' else qs
    def perform_update(self, serializer):
        if self.request.user.role == 'manager' and serializer.instance.role != 'client':
            raise PermissionDenied('Manager faqat mijozni tahrirlay oladi.')
        if serializer.instance.pk == self.request.user.pk and (serializer.validated_data.get('role', 'admin') != 'admin' or serializer.validated_data.get('is_active') is False):
            raise ValidationError('O‘z admin ruxsatingizni olib tashlay olmaysiz.')
        serializer.save()
    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise ValidationError('O‘zingizni o‘chira olmaysiz.')
        super().perform_destroy(instance)

class CarViewSet(SafeModelViewSet):
    serializer_class = CarSerializer
    queryset = Car.objects.select_related('owner').all().order_by('-id')
    search_fields = ['brand', 'model', 'plate_number', 'owner__full_name']
    filterset_fields = ['owner']
    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.role == 'client':
            return qs.filter(owner=user)
        if user.role == 'mechanic':
            return qs.filter(orders__mechanic=user).distinct()
        return qs
    def perform_create(self, serializer):
        if self.request.user.role == 'mechanic':
            raise PermissionDenied()
        serializer.save()
    def perform_update(self, serializer):
        if self.request.user.role == 'mechanic':
            raise PermissionDenied()
        serializer.save()
    def perform_destroy(self, instance):
        staff(self.request.user)
        super().perform_destroy(instance)
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        orders = self.get_object().orders.all()
        if request.user.role == 'mechanic':
            orders = orders.filter(mechanic=request.user)
        return Response(OrderSerializer(orders, many=True).data)

class CatalogViewSet(SafeModelViewSet):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in permissions.SAFE_METHODS:
            staff(request.user)

class ServiceViewSet(CatalogViewSet):
    queryset = Service.objects.all().order_by('name')
    serializer_class = ServiceSerializer
    search_fields = ['name', 'description']
    filterset_fields = ['is_active']

@extend_schema_view(restock=extend_schema(request=RestockSerializer, responses=PartSerializer))
class PartViewSet(CatalogViewSet):
    queryset = Part.objects.all().order_by('name')
    serializer_class = PartSerializer
    search_fields = ['name', 'sku']
    @action(detail=False, url_path='low-stock')
    def low_stock(self, request):
        staff(request.user)
        return Response(self.get_serializer(self.get_queryset().filter(quantity__lte=F('min_quantity')), many=True).data)
    @action(detail=True, methods=['post'])
    def restock(self, request, pk=None):
        with transaction.atomic():
            part = Part.objects.select_for_update().get(pk=self.get_object().pk)
            count = quantity(request.data.get('quantity'))
            part.quantity += count
            part.save()
            StockMovement.objects.create(part=part, change=count, reason='purchase', created_by=request.user)
        return Response(self.get_serializer(part).data)

class StockViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrManager]
    queryset = StockMovement.objects.select_related('part').order_by('-created_at')
    serializer_class = StockSerializer
    filterset_fields = ['part', 'order', 'reason']
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        staff(request.user)

@extend_schema_view(
    diagnose=extend_schema(request=DiagnoseSerializer, responses=OrderSerializer),
    assign=extend_schema(request=AssignSerializer, responses=OrderSerializer),
    start=extend_schema(request=None, responses=OrderSerializer),
    complete=extend_schema(request=None, responses=OrderSerializer),
    cancel=extend_schema(request=CancelSerializer, responses=OrderSerializer),
    pay=extend_schema(request=PaySerializer, responses=OrderSerializer),
    add_service=extend_schema(request=AddServiceSerializer, responses=OrderSerializer),
    add_order_part=extend_schema(request=AddPartSerializer, responses=OrderSerializer),
    remove_item=extend_schema(operation_id='orders_remove_item', responses=OrderSerializer),
)
class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]
    serializer_class = OrderSerializer
    queryset = Order.objects.select_related('client', 'car', 'mechanic').prefetch_related('services__service', 'parts__part', 'payments', 'history__changed_by')
    filterset_fields = ['status', 'client', 'mechanic', 'car']
    search_fields = ['problem_description', 'client__full_name', 'car__plate_number']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == 'client':
            qs = qs.filter(client=user)
        elif user.role == 'mechanic':
            qs = qs.filter(mechanic=user)
        for param, field in [('date_from', 'created_at__date__gte'), ('date_to', 'created_at__date__lte')]:
            value = self.request.query_params.get(param)
            if value:
                from datetime import date
                try:
                    date.fromisoformat(value)
                except ValueError:
                    raise ValidationError('Sana YYYY-MM-DD shaklida bo‘lsin.')
                qs = qs.filter(**{field: value})
        return qs
    @transaction.atomic
    def perform_create(self, serializer):
        staff(self.request.user)
        order = serializer.save(manager=self.request.user)
        OrderStatusHistory.objects.create(order=order, new_status='NEW', changed_by=self.request.user)
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        staff(request.user)
        instance = Order.objects.select_for_update().get(pk=self.get_object().pk)
        editable(instance)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    def destroy(self, request, *args, **kwargs):
        raise ValidationError('Buyurtmani o‘chirish o‘rniga bekor qiling.')
    @action(detail=False)
    def my(self, request):
        return self.list(request)
    @action(detail=True, methods=['post', 'patch'])
    def diagnose(self, request, pk=None):
        return self.transition(request, 'DIAGNOSTICS', diagnosis_notes=request.data.get('diagnosis_notes', ''))
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        staff(request.user)
        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=self.get_object().pk)
            mechanic = get_object_or_404(User, pk=serializer.validated_data['mechanic'], role='mechanic', is_active=True)
            if order.status == 'NEW':
                notes = serializer.validated_data.get('diagnosis_notes', '').strip()
                if not notes:
                    raise ValidationError({'diagnosis_notes': 'Avval diagnostika xulosasini kiriting.'})
                order.diagnosis_notes = notes
                change_status(order, 'DIAGNOSTICS', request.user)
            order.mechanic = mechanic
            change_status(order, 'ASSIGNED', request.user)
        return Response(self.get_serializer(order).data)
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self.transition(request, 'IN_PROGRESS')
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        return self.transition(request, 'COMPLETED')
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=self.get_object().pk)
            change_status(order, 'CANCELLED', request.user, request.data.get('comment', ''))
            for pending in order.part_requests.select_for_update().filter(status='PENDING'):
                pending.status = 'REJECTED'
                pending.reviewed_by = request.user
                pending.reviewed_at = timezone.now()
                pending.save()
            for item in order.parts.select_related('part').order_by('part_id'):
                part = Part.objects.select_for_update().get(pk=item.part_id)
                part.quantity += item.quantity
                part.save()
                StockMovement.objects.create(part=part, order=order, change=item.quantity, reason='return', created_by=request.user)
        return Response(self.get_serializer(order).data)
    def transition(self, request, target, **attrs):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=self.get_object().pk)
            for key, value in attrs.items():
                setattr(order, key, value)
            if target == 'COMPLETED':
                if order.part_requests.filter(status='PENDING').exists():
                    raise ValidationError('Avval kutilayotgan ehtiyot qism so‘rovlarini ko‘rib chiqing.')
                recalculate_total(order)
                if order.total_price <= 0:
                    raise ValidationError('Yakunlashdan oldin xizmat yoki qism qo‘shing.')
            change_status(order, target, request.user)
        return Response(self.get_serializer(order).data)
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = accept_payment(self.get_object().pk, request.data.get('amount'), request.data.get('method'), request.user)
        return Response(self.get_serializer(order).data)
    @action(detail=True, methods=['post'], url_path='services')
    def add_service(self, request, pk=None):
        staff(request.user)
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=self.get_object().pk)
            editable(order)
            service = get_object_or_404(Service, pk=quantity(request.data.get('service')), is_active=True)
            OrderService.objects.create(order=order, service=service, price=service.price, quantity=quantity(request.data.get('quantity', 1)))
            recalculate_total(order)
        return Response(self.get_serializer(order).data)
    @action(detail=True, methods=['post'], url_path='parts')
    def add_order_part(self, request, pk=None):
        order = add_part(self.get_object().pk, request.data.get('part'), request.data.get('quantity', 1), request.user)
        return Response(self.get_serializer(order).data)
    @action(detail=True, methods=['delete'], url_path=r'(?P<kind>services|parts)/(?P<item_id>\d+)')
    def remove_item(self, request, pk=None, kind=None, item_id=None):
        staff(request.user)
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=self.get_object().pk)
            editable(order)
            if kind == 'services':
                staff(request.user)
                item = get_object_or_404(OrderService, pk=item_id, order=order)
            else:
                if request.user.role != 'mechanic' or order.mechanic_id != request.user.pk:
                    staff(request.user)
                item = get_object_or_404(OrderPart, pk=item_id, order=order)
                part = Part.objects.select_for_update().get(pk=item.part_id)
                part.quantity += item.quantity
                part.save()
                StockMovement.objects.create(part=part, order=order, change=item.quantity, reason='return', created_by=request.user)
            item.delete()
            recalculate_total(order)
        return Response(self.get_serializer(order).data)

    @extend_schema(request=WorkLogSerializer, responses=WorkLogSerializer(many=True))
    @action(detail=True, methods=['get', 'post'], url_path='work-logs')
    def work_logs(self, request, pk=None):
        order = self.get_object()
        if request.method == 'POST':
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order.pk)
                editable(order)
                if request.user.role != 'mechanic' or order.mechanic_id != request.user.pk:
                    staff(request.user)
                if order.status not in ('ASSIGNED', 'IN_PROGRESS'):
                    raise ValidationError('Faqat biriktirilgan yoki jarayondagi ishga izoh kiriting.')
                serializer = WorkLogSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                serializer.save(order=order, mechanic=request.user)
        return Response(WorkLogSerializer(order.work_logs.select_related('mechanic'), many=True).data)

    @extend_schema(request=PartRequestSerializer, responses=PartRequestSerializer(many=True))
    @action(detail=True, methods=['get', 'post'], url_path='part-requests')
    def part_requests(self, request, pk=None):
        order = self.get_object()
        if request.user.role == 'client':
            raise PermissionDenied()
        if request.method == 'POST':
            if request.user.role != 'mechanic' or order.mechanic_id != request.user.pk:
                raise PermissionDenied('So‘rovni faqat biriktirilgan usta yuboradi.')
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order.pk)
                editable(order)
                if order.status not in ('ASSIGNED', 'IN_PROGRESS'):
                    raise ValidationError('Buyurtma ishga biriktirilmagan.')
                serializer = PartRequestSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                serializer.save(order=order, requested_by=request.user)
        return Response(PartRequestSerializer(order.part_requests.select_related('part', 'requested_by'), many=True).data)

    @extend_schema(request=ReviewSerializer, responses=ReviewSerializer)
    @action(detail=True, methods=['get', 'post', 'patch'])
    def feedback(self, request, pk=None):
        order = self.get_object()
        if request.method == 'GET':
            review = Review.objects.filter(order=order).first()
            return Response(ReviewSerializer(review).data if review else None)
        if request.user.role != 'client' or order.client_id != request.user.pk:
            raise PermissionDenied('Faqat buyurtma egasi fikr bildiradi.')
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            if order.status not in ('COMPLETED', 'PAID'):
                raise ValidationError('Avval xizmat yakunlanishi kerak.')
            existing = Review.objects.filter(order=order).first()
            if request.method == 'POST' and existing:
                raise ValidationError('Fikr mavjud. Tahrirlashdan foydalaning.')
            if request.method == 'PATCH' and not existing:
                raise ValidationError('Avval fikr yarating.')
            serializer = ReviewSerializer(existing, data=request.data, partial=request.method == 'PATCH')
            serializer.is_valid(raise_exception=True)
            serializer.save(order=order, client=request.user)
        return Response(serializer.data)

    @extend_schema(responses={200: {'type': 'object'}})
    @action(detail=True, methods=['get'])
    def invoice(self, request, pk=None):
        order = self.get_object()
        if request.user.role == 'mechanic':
            raise PermissionDenied()
        if order.status not in ('COMPLETED', 'PAID'):
            raise ValidationError('Hisob-faktura faqat yakunlangan buyurtmaga beriladi.')
        paid = order.payments.aggregate(total=Sum('amount'))['total'] or Decimal(0)
        return Response({'number': f'AS-{order.pk:06d}', 'issued_at': order.created_at, 'order': OrderSerializer(order).data, 'paid': paid, 'balance': order.total_price - paid})

@extend_schema(responses={200: {'oneOf': [{'type': 'object'}, {'type': 'array', 'items': {'type': 'object'}}]}})
@api_view(['GET'])
def report(request, report_name):
    staff(request.user)
    payments = Payment.objects.all()
    today = timezone.localdate()
    if report_name == 'summary':
        return Response({'total_orders': Order.objects.count(), 'active_orders': Order.objects.exclude(status__in=['PAID', 'CANCELLED']).count(), 'clients': User.objects.filter(role='client').count(), 'today_revenue': payments.filter(paid_at__date=today).aggregate(total=Sum('amount'))['total'] or 0, 'month_revenue': payments.filter(paid_at__year=today.year, paid_at__month=today.month).aggregate(total=Sum('amount'))['total'] or 0, 'statuses': list(Order.objects.values('status').annotate(count=Count('id'))), 'low_stock_count': Part.objects.filter(quantity__lte=F('min_quantity')).count()})
    if report_name == 'revenue':
        period = request.query_params.get('period', 'day')
        trunc = {'day': TruncDate, 'week': TruncWeek, 'month': TruncMonth}.get(period)
        if not trunc:
            raise ValidationError('period: day, week yoki month')
        return Response(list(payments.annotate(date=trunc('paid_at')).values('date').annotate(total=Sum('amount')).order_by('date')))
    if report_name == 'top-services':
        return Response(list(OrderService.objects.exclude(order__status='CANCELLED').values('service__name').annotate(count=Sum('quantity')).order_by('-count')[:10]))
    if report_name == 'mechanics':
        return Response(list(User.objects.filter(role='mechanic').annotate(completed=Count('mechanic_orders', filter=Q(mechanic_orders__status__in=['COMPLETED', 'PAID'])), revenue=Sum('mechanic_orders__total_price', filter=Q(mechanic_orders__status='PAID'))).values('id', 'full_name', 'completed', 'revenue')))
    if report_name == 'low-stock':
        return Response(PartSerializer(Part.objects.filter(quantity__lte=F('min_quantity')), many=True).data)
    raise ValidationError('Hisobot topilmadi.')
