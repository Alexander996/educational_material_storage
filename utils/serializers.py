import sqlalchemy as sa

from aiohttp.web_exceptions import HTTPNotFound

from utils.exceptions import ValidationError
from utils.fields import Field, Empty

from utils.fields import (
    IntegerField, CharField, BooleanField
)


class SerializerMeta(type):
    def __new__(mcs, name, bases, attrs):
        fields = [(field_name, attrs.pop(field_name))
                  for field_name, obj in list(attrs.items())
                  if isinstance(obj, Field)]

        for base in reversed(bases):
            if hasattr(base, '_serializer_fields'):
                fields += [(field_name, obj) for field_name, obj
                           in base._serializer_fields.items()
                           if field_name not in attrs]

        attrs['_serializer_fields'] = dict(fields)
        return super(SerializerMeta, mcs).__new__(mcs, name, bases, attrs)


class Serializer(Field, metaclass=SerializerMeta):
    def __init__(self, data=Empty, **kwargs):
        self.initial_data = data
        self.validated_data = {}
        super(Serializer, self).__init__(**kwargs)

    @property
    def fields(self):
        return self._serializer_fields

    def is_valid(self):
        errors = {}

        for field_name, field in self.fields.items():
            if field.read_only:
                continue

            initial_value = self.initial_data.get(field_name, Empty)
            if not field.required and initial_value is Empty:
                continue

            value = field.validate(initial_value)
            if field.validation_error is not None:
                errors[field_name] = field.validation_error
            else:
                self.validated_data[field_name] = value

        if errors:
            raise ValidationError(errors)

    async def to_json(self, result):
        if result.rowcount == 0:
            raise HTTPNotFound

        json = {}
        async for row in result:
            for field_name, value in row.items():
                field = self.fields.get(field_name)
                if field is None or field.write_only:
                    continue

                json_value = field.to_representation(value)
                json[field_name] = json_value

        return json


class ModelSerializerMeta(SerializerMeta):
    _fields_mapping = {
        sa.Integer: IntegerField,
        sa.String: CharField,
        sa.Boolean: BooleanField
    }

    def __new__(mcs, name, bases, attrs):
        if name == 'ModelSerializer':
            return super(ModelSerializerMeta, mcs).__new__(mcs, name, bases, attrs)

        try:
            Meta = attrs['Meta']
        except KeyError:
            raise AttributeError('{} have not Meta'.format(name))

        try:
            model = Meta.model
        except AttributeError:
            raise AttributeError('{}.Meta have not model'.format(name))

        meta_fields = getattr(Meta, 'fields', None)
        if meta_fields is not None and not (meta_fields == '__all__' or isinstance(meta_fields, (list, tuple))):
            raise ValueError('{}.Meta.fields must be list, tuple or "__all__", not {}'
                             .format(name, type(meta_fields).__name__))

        if meta_fields == '__all__':
            meta_fields = [c.name for c in model.columns]
        else:
            meta_fields = set(meta_fields) if meta_fields else None

        meta_exclude = getattr(Meta, 'exclude', None)
        if meta_exclude is not None and not isinstance(meta_exclude, (list, tuple)):
            raise ValueError('{}.Meta.exclude must be list or tuple, not {}'.format(name, type(meta_exclude).__name__))

        meta_exclude = set(meta_exclude) if meta_exclude else None

        assert not (meta_fields is not None and meta_exclude is not None), '{}.Meta must have only fields or exclude'\
                                                                           .format(name)
        assert not (meta_fields is None and meta_exclude is None), '{}.Meta must have at least one attribute ' \
                                                                   'fields or exclude'.format(name)

        for c in model.columns:
            if attrs.get(c.name) is not None:
                continue

            if meta_fields is not None and c.name not in meta_fields:
                continue

            if meta_exclude is not None and c.name in meta_exclude:
                continue

            field_cls = mcs._fields_mapping[c.type.__class__]
            default = c.default if c.default is not None else Empty
            read_only = True if c.name == 'id' else False
            field = field_cls(allow_null=c.nullable, default=default, read_only=read_only)
            attrs[c.name] = field

        return super(ModelSerializerMeta, mcs).__new__(mcs, name, bases, attrs)


class ModelSerializer(Serializer, metaclass=ModelSerializerMeta):
    pass

