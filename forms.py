from django import forms
from django.forms import ModelForm, SelectDateWidget, ModelMultipleChoiceField, Textarea, MultipleChoiceField
from django.contrib.admin.widgets import AdminDateWidget
from django.forms.models import ModelChoiceIterator
from .models import Product, Vendor, Procedure, PurchaseOrder, PO_Item, Lifeline
from django.forms import formset_factory

# Admin SuperUser Event Form
# class EventFormAdmin(ModelForm):
# 	class Meta:
# 		model = Event
# 		fields = ('name', 'event_date', 'venue', 'manager', 'attendees', 'description')
# 		labels = {
# 			'name': '',
# 			'event_date': 'YYYY-MM-DD HH:MM:SS',
# 			'venue': 'Venue',
# 			'manager': 'Manager',
# 			'attendees': 'Attendees',
# 			'description': '',
# 		}
# 		widgets = {
# 			'name': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Event Name'}),
# 			'event_date': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Event Date'}),
# 			'venue': forms.Select(attrs={'class':'form-select', 'placeholder':'Venue'}),
# 			'manager': forms.Select(attrs={'class':'form-select', 'placeholder':'Manager'}),
# 			'attendees': forms.SelectMultiple(attrs={'class':'form-control', 'placeholder':'Attendees'}),
# 			'description': forms.Textarea(attrs={'class':'form-control', 'placeholder':'Description'}),
# 		}

class CleanedTextAreaField(ModelMultipleChoiceField):
	widget = Textarea(attrs={'cols': 100, 'class':'form-control', 'placeholder':'Scan each barcode of product used in procedure:'})
	def clean(self, value):
		if value is not None:
			value = [item.strip() for item in value.split(r'\r\n')]
		return super().clean(value)

class CustomModelChoiceIterator(ModelChoiceIterator):
    def choice(self, obj):
        return (self.field.prepare_value(obj),
                self.field.label_from_instance(obj), obj)

class CustomModelChoiceField(ModelMultipleChoiceField):
    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices
        return CustomModelChoiceIterator(self)
    choices = property(_get_choices,
                       MultipleChoiceField._set_choices)


class DateSelectorForm(forms.Form):
    date_start = forms.DateField(widget=forms.DateInput(attrs=dict(type='date')))
    date_end = forms.DateField(widget=forms.DateInput(attrs=dict(type='date')))

    # 'date': forms.DateInput(
    #     format=('%Y-%m-%d'),
    #     attrs={'class': 'form-control',
    #           'placeholder': 'Select a date',
    #           'type': 'date'
    #           }),
    # }


class ProductNotesForm(ModelForm):
	class Meta:
		model = Product
		fields = ['notes']

class LifelineResponseForm(forms.ModelForm):
    class Meta:
        model = Lifeline
        fields = ['q1_response', 'q2_response', 'q2a_response', 'q2b_response', 'q3_response', 'q3a_response', 'status', 'tag',  'result', 'notes']

    YES = "Yes"
    NO = "No"
    NOT_SELECTED = "Not Selected"

    YES_NO_CHOICES = [
        ('Yes', 'Yes'),
        ('No', 'No'),
        ('Not Selected', 'Not Selected'),
    ]

    N_A_CHOICES = [
        ('Yes', 'Yes'),
        ('No', 'No'),
        ('N/A', 'N/A'),
    ]

    # status
    SPOKEN_TO = "Spoken To"
    UNREACHABLE = "Unable to Reach"
    LEFT_VM = "Left Voicemail"
    NOT_YET_CONTACTED = "Not Yet Contacted"

    # interested
    INTERESTED = "Interested"
    NOT_INTERESTED = "Not interested"
    CALLBACK_REQUESTED = "Patient Requested Callback"
    N_A = "Not Applicable"

    # result
    APPT_SET = "Appointment Set Up with Patient"
    LEFT_ANOTHER_VM = "Left (Another) Voicemail"
    N_L_A = "No Longer Applicable (due to various reasons)"
    UNSET = "Not currently selected"

    STATUS_CHOICES = [
        (SPOKEN_TO, "Spoken To"),
        (UNREACHABLE, "Unable to Reach"),
        (LEFT_VM, "Left Voicemail"),
        (NOT_YET_CONTACTED, "Not Yet Contacted"),
        ]

    TAG_OPTIONS = [
        (INTERESTED, "Interested"),
        (NOT_INTERESTED, "Not interested"),
        (CALLBACK_REQUESTED, "Patient Requested Callback"),
        (N_A, "Not Applicable"),
        ]


    RESULT_OPTIONS = [
        (APPT_SET, "Appointment Set Up with Patient"),
        (LEFT_ANOTHER_VM, "Left (Another) Voicemail"),
        (N_L_A, "No Longer Applicable (due to various reasons)"),
        (UNSET, "Not currently selected"),
        ]


    q1_response = forms.ChoiceField(label="1) Did you get results from the screening?", choices=YES_NO_CHOICES, widget=forms.RadioSelect)
    q2_response = forms.ChoiceField(label="2) Did you review results with your Primary Care Provider or a vascular specialist?", choices=YES_NO_CHOICES, widget=forms.RadioSelect)
    q2a_response = forms.CharField(label="2a) If reviewed: Would you mind sharing who you reviewed your results with, for our records? (name + office contact info)", max_length=256, required=False)
    q2b_response = forms.ChoiceField(label="2b) If reviewed: Was any further testing recommended/pursued?", choices=N_A_CHOICES, widget=forms.RadioSelect, required=False)
    q3_response = forms.ChoiceField(label="3) Would you like to schedule an appointment with Omni Vascular? (for further evaluation or questions)", choices=YES_NO_CHOICES, widget=forms.RadioSelect)
    q3a_response = forms.CharField(label="3a) If yes to schedule: When would be a good time for us to call you to schedule an appointment?", max_length=256, required=False)
    status = forms.ChoiceField(label="Initial Status:", choices=STATUS_CHOICES)
    tag = forms.ChoiceField(label="Interest/Tag:", choices=TAG_OPTIONS)
    result = forms.ChoiceField(label="Post Follow-up:", choices=RESULT_OPTIONS)
    notes = forms.CharField(label="Any additional notes:", widget=forms.Textarea(attrs={'rows': 4, 'cols': 15}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False

    # def process_entry(self):
    #     if self.is_valid():
    #         instance = self.save(commit=False)
    #         instance.processed = True
    #         instance.save()
    #         return True
        # return False

class ProcedureForm(ModelForm):

	class Meta:
		model = Procedure
		fields = ('procedure', 'patient_mrn', 'date_performed', 'qr_codes_used')
		labels = {
		'procedure': "Procedure performed:",
		'patient_mrn': "Patient MRN:",
		'date_performed': "Date of Procedure:",
		'qr_codes_used': "QR Codes of Products used in procedure:",
		# 'choice_field': "Select action to perform on items input:",
		    }

		widgets = {
		'procedure': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Procedure Name'}),
# 		'patient_mrn': forms.IntegerField(attrs={'class':'form-control', 'placeholder':'MRN'}),
# 		'date_performed': forms.DateInput(attrs={'class':'form-select', 'placeholder':'Expiration Date: (MM/DD/YYYY)'}, format="%m/%d/%Y"),
        'date_performed': forms.DateTimeInput(format=('%Y-%m-%dT%H:%M'), attrs={'type': 'datetime-local'}),
		'qr_codes_used': forms.Textarea(attrs={'cols': 100, 'class':'form-control', 'placeholder':'Scan/enter each barcode/QR code of product used'}),
            }
	patient_mrn = forms.IntegerField(widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'MRN'}))


class VendorForm(ModelForm):
	class Meta:
		model = Vendor
		fields = ('id', 'name', 'abbrev')
		labels = {
		'id': "Vendor ID:",
		'name': "Vendor Name:",
		'abbrev': "Vendor Abbreviation:",
		# 'choice_field': "Select action to perform on items input:",
		}
		widgets = {
		'id': forms.NumberInput(attrs={'class':'form-control', 'placeholder':'Vendor ID:'}),
		'name': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Vendor:'}),
		'abbrev': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Vendor abbreviation:'}),
		}

class CommaSeparatedField(forms.Textarea):
    def __init__(self, attrs=None):
        final_attrs = {'cols': 100, 'class':'form-control', 'placeholder':'List of PO items'}
        if attrs is not None:
            final_attrs.update(attrs)
        super().__init__(attrs=final_attrs)
    def to_python(self, value):
        if value in self.empty_values:
            return self.empty_value
        value = str(value).split(',')
        if self.strip:
            value = [s.strip() for s in value]
        return value
    def prepare_value(self, value):
        if value is None:
            return None
        return ', '.join([str(s) for s in value])

# from django.forms import modelformset_factory
class POItemForm(forms.ModelForm):
    class Meta:
        model = PO_Item
        fields = ('name', 'qty_ordered', 'qty_received', 'date_received') #date_ordered removed, as its non-editable field
        labels = {
            'name': 'Name of item',
            'qty_ordered': 'Quantity ordered',
            'qty_received': 'Quantity received',
            # 'date_ordered': 'Date ordered',
            'date_received': 'Date received',
            }
        widgets = {
        'name': forms.TextInput(attrs={'class':'form-control', 'placeholder':'PO Number'}),
        'qty_ordered': forms.NumberInput(
			    attrs={
			        'class': 'form-control',
			        'placeholder': 'Quantity ordered',
			        'min': '0',  # Minimum value allowed for the input
			        'step': '1',  # Step value for increment and decrement
			        'id': 'id_quantity_ordered',
			    },
			),
        'qty_received': forms.NumberInput(
			    attrs={
			        'class': 'form-control',
			        'placeholder': 'Quantity received',
			        'min': '0',  # Minimum value allowed for the input
			        'step': '1',  # Step value for increment and decrement
			        'id': 'id_quantity_received',
			    },
			),
        # 'date_ordered': forms.DateInput(attrs={'type': 'date'}),
        'date_received': forms.DateInput(attrs={'type': 'date'}),
        }

class PurchaseOrderForm(ModelForm):

    class Meta:
        model = PurchaseOrder
        fields = ('vendor', 'po_date', 'status', 'notes') # removed po_number as its now auto-generated, 11/30/2023
        # removed status from po creation, now defaults to "Created", 02/14/2024
        labels = {
            # 'po_number': 'Purchase Order #: (ensure unique)', #also add this to fields when re-introducing to form
            'vendor': 'Vendor ID',
            # 'po_items_list': 'Enter Items in this PO',
            'po_date': 'Date of Purchase Order',
            'status': 'Current status of PO',
            'notes': 'PO Notes',
            }
        widgets = {
        # 'po_number': forms.TextInput(attrs={'class':'form-control', 'placeholder':'PO Number'}),
        'vendor': forms.Select(attrs={'class':'form-select', 'placeholder':'Vendor'}),
        'po_date': forms.DateTimeInput(format=('%Y-%m-%dT%H:%M'), attrs={'type': 'datetime-local'}),
        'status': forms.Select(attrs={'class':'form-select'}),
        }
    notes = forms.CharField(initial="")
    # po_items_list = POItemFormSet(),
    def __init__(self, *args, **kwargs):
        readonly_fields = kwargs.pop('readonly_fields', [])
        dynamic_m2m = kwargs.pop('dynamic_m2m', None)
        po_id = kwargs.pop('po_id', None)
        super(PurchaseOrderForm, self).__init__(*args, **kwargs)
        # for field in readonly_fields:
        #     self.fields[field].initial = getattr(product, field)
        #     self.fields[field].widget.attrs['readonly'] = True
        # if dynamic_m2m:
        #     self.fields['po_items'] = CustomModelChoiceField(queryset=PurchaseOrder.objects.get(id=po_id).po_items.all(), widget=forms.CheckboxSelectMultiple,)
        #     po_items = PurchaseOrder.objects.get(id=po_id).po_items.all()
        #     # for index, item in enumerate(po_items):
        #     #     self.field[f'item_{index}_name'] =
        #     #     self.field[f'item_{index}_qty_ordered'] =
        #     #     self.field[f'item_{index}_qty_received'] =
        #     #     self.field[f'item_{index}_date_ordered'] =
        #     #     self.field[f'item_{index}_date_received'] =
        #     for index, item in enumerate(po_items):
        #         # Add a CharField for the name
        #         self.fields[f'item_{index}_name'] = forms.CharField(initial=item.name, widget=forms.TextInput(attrs={}))
        #         self.fields[f'item_{index}_qty_ordered'] = forms.IntegerField(initial=item.qty_ordered, widget=forms.NumberInput(attrs={}))
        #         self.fields[f'item_{index}_qty_received'] = forms.IntegerField(initial=item.qty_received, widget=forms.NumberInput(attrs={}))
        #         self.fields[f'item_{index}_date_ordered'] = forms.DateTimeField(initial=item.date_ordered, widget=forms.DateInput(attrs={'type': 'date'}))
        #         self.fields[f'item_{index}_date_received'] = forms.DateTimeField(initial=item.date_received,widget=forms.DateInput(attrs={'type': 'date'}))


        for field in readonly_fields:
    	    self.fields[field].disabled = True


# Product Form
class ProductForm(ModelForm):
	class Meta:
		model = Product
		fields = ('name', 'reference_id', 'expiry_date', 'size', 'quantity_on_hand', 'is_purchased', 'notes', 'barcode', 'lot_number', 'vendor')
		labels = {
		'name': 'Product Name:',
		'reference_id': 'Reference ID:',
		'expiry_date': 'Expiration Date:',
		'size': 'Size:',
		'quantity_on_hand': 'Quantity currently on hand:',
		'is_purchased': 'Item is Purchased:',
		'barcode': 'Barcode:',
		'lot_number': 'Lot Number:',
		'vendor': 'Vendor ID:',
		'notes': 'Notes:',
# 		'last_modified': 'Date of last (quantity) edit:',
		}
		widgets = {
			'name': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Product Name'}),
			'vendor': forms.Select(attrs={'class':'form-select', 'placeholder':'Vendor'}),
			'reference_id': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Reference ID'}),
# 			'expiry_date': forms.DateInput(attrs={'class':'form-select', 'placeholder':'Expiration Date: (MM/DD/YYYY)'}, format="%m/%d/%Y"),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
			'size': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Size'}),
			# 'quantity_on_hand': forms.NumberInput(attrs={'class':'form-control', 'placeholder':'Quantity available'}),
			'quantity_on_hand': forms.NumberInput(
			    attrs={
			        'class': 'form-control',
			        'placeholder': 'Quantity available',
			        'min': '0',  # Minimum value allowed for the input
			        'step': '1',  # Step value for increment and decrement
			        'id': 'id_quantity_on_hand',
			    },
			),
			'is_purchased': forms.RadioSelect(),
			'barcode': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Product barcode'}),
			'lot_number': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Product Lot Number'}),
# 			'last_modified': forms.DateInput(attrs={'type': 'date'}),

		}
	notes = forms.CharField(initial="")



	def __init__(self, *args, **kwargs):
		readonly_fields = kwargs.pop('readonly_fields', [])
		super().__init__(*args, **kwargs)
        # for field in readonly_fields:
        #     self.fields[field].initial = getattr(product, field)
        #     self.fields[field].widget.attrs['readonly'] = True
		for field in readonly_fields:
			self.fields[field].disabled = True
# 	expiry_date = forms.DateField(widget=SelectDateWidget(empty_label=("Choose Year", "Choose Month", "Choose Day"),),)

class UneditableProductForm(ProductForm):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['reference_id'].widget.attrs['disabled'] = True
		self.fields['expiry_date'].widget.attrs['disabled'] = True
		self.fields['vendor'].widget.attrs['disabled'] = True
		self.fields['name'].widget.attrs['disabled'] = True
		self.fields['size'].widget.attrs['disabled'] = True




