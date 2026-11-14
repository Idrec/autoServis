from datetime import date
from decimal import Decimal
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer
from .models import User, Car, Service, Part, Order, OrderService, OrderPart, Payment, OrderStatusHistory, StockMovement, RepairRequest, PartRequest, WorkLog, Review, AuditEvent

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'phone', 'role', 'is_active', 'password']
    def validate_password(self, value):
        validate_password(value)
        return value
    def create(self, validated_data):
        if not validated_data.get('password'):
            raise serializers.ValidationError({'password': 'Parol kerak.'})
        return User.objects.create_user(**validated_data)
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save()
        return instance

class CarSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    class Meta:
        model = Car
        fields = '__all__'
    def validate_year(self, value):
        if not 1900 <= value <= date.today().year + 1:
            raise serializers.ValidationError('Avtomobil yili noto‘g‘ri.')
        return value
    def validate_plate_number(self, value):
        return value.upper().strip()
    def validate_owner(self, value):
        if value.role != 'client' or not value.is_active:
            raise serializers.ValidationError('Faol mijozni tanlang.')
        return value
    def validate(self, attrs):
        user = self.context['request'].user
        if user.role == 'client' and attrs.get('owner', user).pk != user.pk:
            raise serializers.ValidationError('Faqat o‘z avtomobilingizni boshqarishingiz mumkin.')
        if self.instance and self.instance.orders.exists() and attrs.get('owner', self.instance.owner) != self.instance.owner:
            raise serializers.ValidationError('Tarix mavjud: egani o‘zgartirib bo‘lmaydi.')
        return attrs

class ServiceSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    estimated_hours = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal('0.01'), required=False)
    class Meta:
        model = Service
        fields = '__all__'

class PartSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    class Meta:
        model = Part
        fields = '__all__'
        read_only_fields = ['quantity']
    def validate(self, attrs):
        if 'quantity' in self.initial_data:
            raise serializers.ValidationError('Qoldiqni kirim orqali o‘zgartiring.')
        return attrs

class OrderServiceSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='service.name')
    class Meta:
        model = OrderService
        fields = ['id', 'service', 'name', 'price', 'quantity']

class OrderPartSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='part.name')
    class Meta:
        model = OrderPart
        fields = ['id', 'part', 'name', 'price', 'quantity']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'

class HistorySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='changed_by.full_name')
    class Meta:
        model = OrderStatusHistory
        fields = '__all__'

class StockSerializer(serializers.ModelSerializer):
    part_name = serializers.CharField(source='part.name')
    class Meta:
        model = StockMovement
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    car_name = serializers.SerializerMethodField()
    plate_number = serializers.CharField(source='car.plate_number', read_only=True)
    mechanic_name = serializers.CharField(source='mechanic.full_name', read_only=True, default='')
    services = OrderServiceSerializer(many=True, read_only=True)
    parts = OrderPartSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    history = HistorySerializer(many=True, read_only=True)
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['manager', 'mechanic', 'status', 'total_price', 'closed_at', 'diagnosis_notes']
    def get_car_name(self, obj) -> str:
        return f'{obj.car.brand} {obj.car.model}'
    def validate(self, attrs):
        client = attrs.get('client', getattr(self.instance, 'client', None))
        car = attrs.get('car', getattr(self.instance, 'car', None))
        if car and client and (car.owner_id != client.id or client.role != 'client'):
            raise serializers.ValidationError('Mashina tanlangan mijozga tegishli emas.')
        return attrs

class RegisterSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        read_only_fields = ['role', 'is_active']

class PasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField()

class ProfileSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)

class DiagnoseSerializer(serializers.Serializer):
    diagnosis_notes = serializers.CharField()

class AssignSerializer(serializers.Serializer):
    mechanic = serializers.IntegerField(min_value=1)
    diagnosis_notes = serializers.CharField(required=False, allow_blank=True)

class AddServiceSerializer(serializers.Serializer):
    service = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, default=1)

class AddPartSerializer(serializers.Serializer):
    part = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, default=1)

class RestockSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)

class PaySerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    method = serializers.ChoiceField(choices=['cash', 'card', 'transfer'])

class CancelSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False)

class CustomerSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        read_only_fields = ['role', 'is_active']
    def validate(self, attrs):
        forbidden = set(self.initial_data) - {'username', 'password', 'full_name', 'email', 'phone'}
        if forbidden:
            raise serializers.ValidationError('Manager faqat mijoz profilini boshqaradi; rol va bloklash admin uchun.')
        return attrs
    def create(self, validated_data):
        validated_data['role'] = 'client'
        return super().create(validated_data)

class RepairRequestSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    car_name = serializers.SerializerMethodField()
    class Meta:
        model = RepairRequest
        fields = '__all__'
        read_only_fields = ['client', 'status', 'order', 'response_note', 'created_at', 'reviewed_by']
    def get_car_name(self, obj) -> str:
        return f'{obj.car.brand} {obj.car.model} · {obj.car.plate_number}'
    def validate_car(self, car):
        if car.owner_id != self.context['request'].user.pk:
            raise serializers.ValidationError('Faqat o‘z avtomobilingiz uchun so‘rov yuboring.')
        return car

@extend_schema_serializer(component_name='PartRequisition')
class PartRequestSerializer(serializers.ModelSerializer):
    part_name = serializers.CharField(source='part.name', read_only=True)
    mechanic_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    quantity = serializers.IntegerField(min_value=1)
    class Meta:
        model = PartRequest
        fields = '__all__'
        read_only_fields = ['order', 'requested_by', 'status', 'reviewed_by', 'reviewed_at', 'created_at']

class WorkLogSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(source='mechanic.full_name', read_only=True)
    minutes = serializers.IntegerField(min_value=0, max_value=1440, default=0)
    class Meta:
        model = WorkLog
        fields = '__all__'
        read_only_fields = ['order', 'mechanic', 'created_at']
    def validate(self, attrs):
        if not any(attrs.get(k) for k in ['diagnosis', 'additional_faults', 'comment', 'minutes']):
            raise serializers.ValidationError('Izoh, nosozlik, diagnostika yoki sarflangan vaqtni kiriting.')
        return attrs

class ReviewSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['client', 'order', 'created_at']

class RequestDecisionSerializer(serializers.Serializer):
    response_note = serializers.CharField(required=False, allow_blank=True)

class AuditSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True, default='')
    class Meta:
        model = AuditEvent
        fields = '__all__'
