from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, mixins
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .models import User, Car, Order, OrderStatusHistory, PartRequest, RepairRequest, Payment, Part, AuditEvent, WorkLog
from .serializers import RepairRequestSerializer, RequestDecisionSerializer, PartRequestSerializer, AuditSerializer
from .services import staff, add_part, change_status


class RepairRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = RepairRequestSerializer
    queryset = RepairRequest.objects.select_related('client', 'car').all()
    filterset_fields = ['status', 'client']
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == 'client':
            return qs.filter(client=self.request.user)
        if self.request.user.role == 'mechanic':
            return qs.none()
        return qs
    def perform_create(self, serializer):
        if self.request.user.role != 'client':
            raise PermissionDenied('Bu bo‘lim mijoz so‘rovlari uchun.')
        serializer.save(client=self.request.user)
    @extend_schema(request=RequestDecisionSerializer, responses=RepairRequestSerializer)
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        staff(request.user)
        with transaction.atomic():
            obj = RepairRequest.objects.select_for_update().get(pk=self.get_object().pk)
            if obj.status != 'PENDING':
                raise ValidationError('So‘rov allaqachon ko‘rib chiqilgan.')
            if obj.car.owner_id != obj.client_id:
                raise ValidationError('Avtomobil egasi o‘zgargan.')
            order = Order.objects.create(client=obj.client, car=obj.car, manager=request.user, problem_description=obj.description)
            OrderStatusHistory.objects.create(order=order, new_status='NEW', changed_by=request.user)
            obj.status = 'ACCEPTED'
            obj.order = order
            obj.reviewed_by = request.user
            obj.response_note = str(request.data.get('response_note', ''))
            obj.save()
        return Response(self.get_serializer(obj).data)
    @extend_schema(request=RequestDecisionSerializer, responses=RepairRequestSerializer)
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        staff(request.user)
        with transaction.atomic():
            obj = RepairRequest.objects.select_for_update().get(pk=self.get_object().pk)
            if obj.status != 'PENDING':
                raise ValidationError('So‘rov allaqachon ko‘rib chiqilgan.')
            obj.status = 'REJECTED'
            obj.reviewed_by = request.user
            obj.response_note = str(request.data.get('response_note', ''))
            obj.save()
        return Response(self.get_serializer(obj).data)


class PartRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PartRequestSerializer
    queryset = PartRequest.objects.select_related('part', 'requested_by').all()
    filterset_fields = ['status', 'order']
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == 'mechanic':
            return qs.filter(requested_by=self.request.user, order__mechanic=self.request.user)
        if self.request.user.role == 'client':
            return qs.none()
        return qs
    @extend_schema(request=None, responses=PartRequestSerializer)
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        staff(request.user)
        original = self.get_object()
        with transaction.atomic():
            # Same lock order as all order/stock changes: order, request, part.
            Order.objects.select_for_update().get(pk=original.order_id)
            obj = PartRequest.objects.select_for_update().get(pk=original.pk)
            if obj.status != 'PENDING':
                raise ValidationError('So‘rov allaqachon ko‘rib chiqilgan.')
            if obj.order.mechanic_id != obj.requested_by_id:
                raise ValidationError('Buyurtma boshqa ustaga o‘tkazilgan.')
            add_part(obj.order_id, obj.part_id, obj.quantity, request.user)
            obj.status = 'APPROVED'
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
            obj.save()
        return Response(self.get_serializer(obj).data)
    @extend_schema(request=None, responses=PartRequestSerializer)
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        staff(request.user)
        original = self.get_object()
        with transaction.atomic():
            Order.objects.select_for_update().get(pk=original.order_id)
            obj = PartRequest.objects.select_for_update().get(pk=original.pk)
            if obj.status != 'PENDING':
                raise ValidationError('So‘rov allaqachon ko‘rib chiqilgan.')
            obj.status = 'REJECTED'
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
            obj.save()
        return Response(self.get_serializer(obj).data)


class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditSerializer
    queryset = AuditEvent.objects.select_related('actor').all()
    filterset_fields = ['entity', 'action', 'actor']
    search_fields = ['detail', 'actor__full_name']
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.role != 'admin':
            raise PermissionDenied()


@extend_schema(responses={200: {'type': 'object'}})
@api_view(['GET'])
def dashboard(request):
    user = request.user
    orders = Order.objects.all()
    if user.role == 'mechanic':
        orders = orders.filter(mechanic=user)
    elif user.role == 'client':
        orders = orders.filter(client=user)
    today = timezone.localdate()
    stats = {
        'total_orders': orders.count(),
        'today_orders': orders.filter(created_at__date=today).count(),
        'new_orders': orders.filter(status='NEW').count(),
        'assigned_orders': orders.filter(status='ASSIGNED').count(),
        'in_progress': orders.filter(status='IN_PROGRESS').count(),
        'waiting_orders': orders.filter(status__in=['NEW', 'DIAGNOSTICS', 'ASSIGNED']).count(),
        'active_orders': orders.exclude(status__in=['PAID', 'CANCELLED']).count(),
        'completed_orders': orders.filter(status__in=['COMPLETED', 'PAID']).count(),
        'awaiting_payment': orders.filter(status='COMPLETED').count(),
        'statuses': list(orders.values('status').annotate(count=Count('pk'))),
    }
    if user.role in ('admin', 'manager'):
        stats.update({'clients': User.objects.filter(role='client').count(), 'cars': Car.objects.count(), 'total_revenue': Payment.objects.aggregate(total=Sum('amount'))['total'] or 0, 'stock_items': Part.objects.count(), 'stock_units': Part.objects.aggregate(total=Sum('quantity'))['total'] or 0, 'pending_repair_requests': RepairRequest.objects.filter(status='PENDING').count(), 'pending_part_requests': PartRequest.objects.filter(status='PENDING').count()})
    elif user.role == 'client':
        stats.update({'cars': user.cars.count(), 'pending_repair_requests': user.repair_requests.filter(status='PENDING').count()})
    else:
        stats.update({'pending_part_requests': PartRequest.objects.filter(requested_by=user, status='PENDING', order__mechanic=user).count(), 'work_minutes': WorkLog.objects.filter(mechanic=user).aggregate(total=Sum('minutes'))['total'] or 0})
    return Response(stats)
