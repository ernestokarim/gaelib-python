
import re

import webapp2
from webapp2_extras import json


class Form(object):
  field_values = {}

  def __init__(self, form_name='f', submit_func='submit', try_submit_func='',
      data_obj='data'):
    self.form_name = form_name
    self.submit_func = submit_func
    self.try_submit_func = try_submit_func
    self.data_obj = data_obj

  def build(self):
    fields = ''.join([f.build(self) for f in self.fields])

    return """
      <form class="form-horizontal" name="%(form_name)s" novalidate
          ng-init="%(form_name)s.val = false;"
          ng-submit="%(form_name)s.$valid && %(submit_func)s()">
        <fieldset>%(fields)s</fieldset>
      </form>
    """ % {
      'form_name': self.form_name,
      'submit_func': self.submit_func,
      'fields': fields,
    }

  def validate(self):
    request = webapp2.get_request()
    data = json.decode(request.body)

    if not isinstance(data, dict):
      webapp2.abort(403, detail='not a dict')

    for f in self.fields:
      if not f.id in self.validations:
        continue

      try:
        value = data[f.id].strip()
      except KeyError:
        value = ''

      self.field_values[f.id] = value
      for val in self.validations[f.id]:
        val.input = f.id

        if not val.validate(self):
          webapp2.abort(403, 
            detail='validation error, id: %s name: %s value: %s' 
            % (f.id, f.name, value))

    return self.field_values

  @property
  def fields(self):
    raise NotImplemented()

  @property
  def validations(self):
    raise NotImplemented()

  def field(self, id):
    if not id in self.field_values:
      return ''

    if isinstance(self.field_values[id], basestring):
      return self.field_values[id]

    request = webapp2.get_request()
    webapp2.abort(403, detail='not a string, id: %s' % id)


class Validation(object):
  """Base class for all form validations."""

  """ID of the input field associated to this validation."""
  input = ""

  def __init__(self, name, message, attrs):
    self.name = name
    self.message = message
    self.attrs = attrs

  def validate(self, form):
    raise NotImplemented()


class LargerThan(Validation):
  def __init__(self, min, message):
    super(LargerThan, self).__init__("minlength", message, 
        {"ng-minlength" : min})
    self.min = min

  def validate(self, form):
    return len(form.field(self.input)) >= self.min


class ShorterThan(Validation):
  def __init__(self, max, message):
    super(ShorterThan, self).__init__("maxlength", message,
        {"ng-maxlength" : max})
    self.max = max

  def validate(self, form):
    return len(form.field(self.input)) <= self.max


class Required(Validation):
  def __init__(self, message):
    super(Required, self).__init__("required", message, {"required": ''})

  def validate(self, form):
    return len(form.field(self.input)) > 0


class Email(Validation):
  def __init__(self, message):
    super(Email, self).__init__("email", message, {})

  def validate(self, form):
    return not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}$', 
        form.field(self.input)) is None


class Match(Validation):
  def __init__(self, field, message):
    super(Match, self).__init__("match", message, {'match': field})
    self.field = field

  def validate(self, form):
    return form.field(self.field) == form.field(self.input)


class Pattern(Validation):
  def __init__(self, pattern, message):
    super(Pattern, self).__init__("pattern", message, {"pattern" : pattern})
    self.pattern = pattern

    def validate(self, form):
      return not re.match(pattern,form.field(self.input)) is None


class Field(object):
  def __init__(self, id, name):
    self.id = id
    self.name = name

  def build(self, form):
    vals = form.validations[self.id]
    id = '%s%s' % (form.form_name, self.id)

    errs = []
    for val in vals:
      errs.append('%s.%s.$error.%s' % (form.form_name, id, val.name))
    errs = " || ".join(errs)

    attrs = {}
    for val in vals:
      attrs.update(val.attrs)

    messages = []
    for v in vals:
      messages.append('<span ng-show="%s.%s.$error.%s">%s</span>' % 
          (form.form_name, id, v.name, v.message))
    messages = ''.join(messages)

    if len(self.name) == 0:
      return attrs, """
        <div class="control-group"
            ng-class="%(form_name)s.val && (%(errs)s) && 'error'">
          %%s
          <p class="help-block error"
              ng-show="%(form_name)s.val && %(form_name)s.%(id)s.$invalid">
            %(messages)s
          </p>
        </div>
      """ % {
        'errs': errs,
        'id': id,
        'form_name': form.form_name,
        'messages': messages,
      }

    return attrs, """
      <div class="control-group"
          ng-class="%(form_name)s.val && (%(errs)s) && 'error'">
        <label class="control-label" for="%(id)s">%(name)s</label>
        <div class="controls">
          %%s
          <p class="help-block error"
              ng-show="%(form_name)s.val && %(form_name)s.%(id)s.$invalid">
            %(messages)s
          </p>
        </div>
      </div>
    """ % {
      'errs': errs,
      'id': id,
      'form_name': form.form_name,
      'messages': messages,
      'name': self.name,
    }


class InputField(Field):
  def __init__(self, id, cls, name, type='text', placeholder=''):
    super(InputField, self).__init__(id, name)

    self.type = type
    self.placeholder = placeholder
    self.cls = cls

  def build(self, form):
    attrs = {
      "type": self.type,
      "id": '%s%s' % (form.form_name, self.id),
      "name": '%s%s' % (form.form_name, self.id),
      "placeholder": self.placeholder,
      "class": ' '.join(self.cls),
      "ng-model": '%s.%s' % (form.data_obj, self.id),
    }
    
    (at, tmpl) = super(InputField, self).build(form)
    attrs.update(at)
    
    input = [' %s="%s"' % (k, v) for k,v in attrs.iteritems()]
    input = '<input%s>' % ''.join(input)

    return tmpl % input


class TextAreaField(Field):
  def __init__(self, id, cls, name, rows, placeholder=''):
    super(InputField, self).__init__(id, name)

    self.placeholder = placeholder
    self.cls = cls
    self.rows = rows

  def build(self, form):
    attrs = {
      "id": '%s%s' % (form.form_name, self.id),
      "name": '%s%s' % (form.form_name, self.id),
      "placeholder": self.placeholder,
      "class": ' '.join(self.cls),
      "ng-model": '%s.%s' % (form.data_obj, self.id),
      "rows": self.rows,
    }
    
    (at, tmpl) = super(TextAreaField, self).build(form)
    attrs.update(at)
    
    input = [' %s="%s"' % (k, v) for k,v in attrs.iteritems()]
    input = '<textarea%s></textarea>' % ''.join(input)

    return tmpl % input


class SubmitField(Field):
  def __init__(self, label):
    super(SubmitField, self).__init__('submit', 'submit')

    self.label = label

  def build(self, form):
    attrs = {
      "label": self.label,
    }

    if len(form.try_submit_func) > 0:
      t = '%s(); ' % form.try_submit_func
    else:
      t = ''
    
    submit = '''
      <div class="form-actions">
        <button ng-click="%(try)s%(form_name)s.val = true;"
            class="btn btn-primary"
            ng-disabled="%(form_name)s.val && !%(form_name)s.$valid">
          %(label)s
        </button>
      </div>
    ''' % {
      'form_name': form.form_name,
      'label': self.label,
      'try': t,
    }

    return submit
