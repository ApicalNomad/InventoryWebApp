from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Vendor, Procedure, PO_Item, PurchaseOrder, Lifeline
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from .tkinter_test import gui

# from django.utils import timezone
from datetime import datetime, timedelta
import pytz

# import json
from .forms import (
    ProductForm,
    ProcedureForm,
    VendorForm,
    PurchaseOrderForm,
    DateSelectorForm,
    POItemForm,
    ProductNotesForm,
    LifelineResponseForm,
)

# from .forms import UneditableProductForm
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)  # , HttpResponseNotAllowed
from django.urls import reverse
from django.contrib import messages
# from calendar import HTMLCalendar
# import calendar

# from django.core import serializers
# from django.views.decorators.cache import cache_control
import traceback

# import qrcode as qr
# import re
from .utils import (
    get_data_from_api,
    update_db_from_inventory_csv,
    update_product_in_sheets,
    construct_or_search_query,
    construct_and_search_query,
    items_added_30days,
    items_used_30days,
    recompose_date,
    create_procedure_objects_from_sheets_data,
    add_product_to_sheets,
    create_po_objects_from_sheets_data,
    sorting_histories,
    update_db_from_inventory_df
)
import threading
import time
import pandas as pd
from dateutil import parser
from django.contrib.auth.decorators import login_required

# import ast


thread_lock = threading.Lock()


@login_required
def all_products(request):
    product_list = Product.objects.all()
    return render(request, "pydb4/product_list.html", {"product_list": product_list})


@login_required
def all_products_used(request):
    product_list = Product.objects.filter(quantity_on_hand=0)
    return render(
        request, "pydb4/product_list_used.html", {"product_list": product_list}
    )


@login_required
def all_products_expired_still_stocked(request):
    product_list = Product.objects.filter(
        expiry_date__lte=datetime.now(), quantity_on_hand__gte=1
    )
    return render(
        request,
        "pydb4/product_list_expired_stocked.html",
        {"product_list": product_list},
    )


@login_required
def all_vendors(request):
    vendor_list = Vendor.objects.all()
    return render(
        request,
        "pydb4/vendor_list.html",
        {"vendor_list": vendor_list},
    )


@login_required
def gui_test(request):
    gui()
    product_list = Product.objects.all()
    return render(request, "pydb4/product_list.html", {"product_list": product_list})


@login_required
def database_update_current_inventory(request):
    with thread_lock:
        try:
            # changing this to use dataframe as source, not csv file
            data = get_data_from_api(
                ["Current Inventory", False], rename_cols=True
            )
            update_db_from_inventory_df(
                data, request.user
            )  # this will pass CSV file to db update function, now along with user
            product_list = Product.objects.all()
            messages.success(
                request,
                "Current inventory updated from CSV, please wait 1-2 minutes before new search.",
            )
            return render(
                request,
                "pydb4/product_list.html",
                {"product_list": product_list},
            )
        except Exception as e:
            traceback.print_exc()
            messages.error(
                request,
                "Error with updating current inventory, please see stack trace and refer to IT admin.",
            )
            product_list = Product.objects.all()
            return render(
                request,
                "pydb4/product_list.html",
                {"product_list": product_list},
            )


# views.process_lifeline_response2
# 05/30/2024: retiring this below, now implementing randomizing logic to every lifeline response start page
# 06/20/2024: randomizing effect not working properly (causes synchronization issues, patient obj sent to server is not same as what's loaded
# in browser DOM), turning this back on.
def process_lifeline_response2(request):
    removal_criteria = Q(status__icontains='Unable to Reach') | Q(tag__icontains='Not interested') | Q(followup_calls__gte=3) # | Q(q3_response__icontains="No") | Q(name__icontains='zee') | Q(notes__icontains='called')
    patient = Lifeline.objects.filter(processed=False).exclude(removal_criteria).last()
    # from random import choice
    # pks = Lifeline.objects.filter(processed=False).values_list('pk', flat=True)
    # random_pk = choice(pks)
    # patient = Lifeline.objects.get(pk=random_pk)
    print(request)
    if request.method == 'POST':
        print(request.POST)
        form = LifelineResponseForm(request.POST, instance=patient)
        print('this is bool of process lifeline response 1, form.valid ', form.is_valid())
        print(form.errors.as_data())
        if form.is_valid():
            result = form.save(commit=False)
            print('lifelineresponse submitted patient: ', patient)
            # disregard = request.POST.get("status") == "Unable to Reach"
            # result.status = request.POST.get("status")
            # result.tag = request.POST.get("tag")
            # result.result = request.POST.get("result")
            print(f'this is processed var of result obj, before being saved: {result.processed}, and this is form: {form}')
            result.processed = True
            result.save()
            print(f'and after save: {result.processed}')
            return redirect('process_lifeline_response2')
        else:
            # print(form.errors.as_data())
            messages.error(request,"Error with form submission, please see stack trace and refer to IT admin.",)
            return redirect('process_lifeline_response2')
    else:
        form = LifelineResponseForm(instance=patient, initial={'q1_response': 'Not Selected', 'q2_response': 'Not Selected','q2b_response': 'N/A', 'q3_response': 'Not Selected', 'status': 'Not Yet Contacted',})

    return render(request, 'pydb4/lifeline_response_form2.html', {'form': form, 'patient': patient})


def process_lifeline_response(request):
    # Get the next patient who has not been processed
    removal_criteria = Q(status__icontains='Unable to Reach') | Q(tag__icontains='Not interested') | Q(followup_calls__gte=3) # | Q(q3_response__icontains="No") | Q(name__icontains='zee') | Q(notes__icontains='called')

    patient = Lifeline.objects.filter(processed=False).exclude(removal_criteria).first()
    # 06/19/2024: above patient works, simple .first() approach, testing new below: --didn't work, trying new, not yet
    # patient = Lifeline.objects.filter(processed=False).exclude(removal_criteria).order_by('?').first()

    # patient = Lifeline.objects.filter(processed=False).first()
    # from random import choice
    # pks = Lifeline.objects.filter(processed=False).values_list('pk', flat=True)
    # random_pk = choice(pks)
    # patient = Lifeline.objects.get(pk=random_pk)
    print(request)
    print('this is session id, per user?:', request.session.session_key)
    if request.method == 'POST':
        print(request.POST)
        form = LifelineResponseForm(request.POST, instance=patient)
        # form = LifelineResponseForm(request.POST)
        print('this is bool of process lifeline response 1, form.valid ', form.is_valid())
        print(form.errors.as_data())
        if form.is_valid():
            result = form.save(commit=False)
            # model_fields = Lifeline._meta.get_fields()
            # for k in request.POST.keys():
            #     if k in
            print('lifelineresponse submitted patient: ', patient)
            print('result variable:', result)
            print(f'this is processed var of result obj, before being saved: {result.processed}, and this is form: {form}')
            result.processed = True
            result.save()
            print(f'processed/name/notes/status/tag after save: {result.processed}, {result.name}, {result.notes}, {result.status}, {result.tag}')
            return redirect('process_lifeline_response')
        else:
            # print(form.errors.as_data())
            messages.error(request,"Error with form submission, please see stack trace and refer to IT admin.",)
            return redirect('process_lifeline_response')
    else:
        form = LifelineResponseForm(instance=patient, initial={'q1_response': 'Not Selected', 'q2_response': 'Not Selected','q2b_response': 'N/A', 'q3_response': 'Not Selected', 'status': 'Not Yet Contacted',})
        return render(request, 'pydb4/lifeline_response_form.html', {'form': form, 'patient': patient})

def vendors_pending(request):
    # vendors = Vendor.objects.filter(purchaseorder__status__icontains='Pending').order_by("")
    # pending_pos = PurchaseOrder.objects.filter(status__icontains='Pending').order_by('po_date')
    # need these aspects passed along to template:
    # 1) qs of vendors without pending PO's
    # 2) qs of vendors WITH pending PO's
    # 3) each pending vendor's PO objects --- maybe able to get this on template
    now = datetime.now(tz=pytz.timezone("US/Eastern")).strftime('%m-%d-%Y')
    pending_vendors = Vendor.objects.filter(purchaseorder__status__icontains='Pending').distinct().order_by('-last_ordered')
    # pending_vendors_with_pos = [(x, list(PurchaseOrder.objects.filter(vendor=x, status__icontains='Pending'))) for x in pending_vendors]
    non_pending_vendors = Vendor.objects.exclude(purchaseorder__status__icontains='Pending')
    pending_vendor_pos_dict = [{x:PurchaseOrder.objects.filter(vendor=x, status__icontains='Pending')} for x in pending_vendors]


    return render(
        request,
        "pydb4/vendors_po_pending.html",
        {"non_pending_vendors": non_pending_vendors,
        "pending_vendor_pos": pending_vendor_pos_dict,
        "now": now
        },
    )


def lifelines_for_followup(request):
    prior = timedelta(days=8)
    now = datetime.now(tz=pytz.timezone("US/Eastern"))
    removal_criteria = Q(result='Appointment Set Up with Patient') | Q(status='Unable to Reach') | Q(tag='Not interested') | Q(followup_calls__gte=3) #| Q(q3_response__icontains="No") #& ~Q(tag__icontains="Patient Requested Callback")
    lifeline_followup = Lifeline.objects.filter(processed=True, accessed__lte=(now-prior)).exclude(removal_criteria).first()
    # lifeline_followup = Lifeline.objects.filter(processed=True, accessed__lte=now).exclude(removal_criteria).order_by("accessed").filter(name__icontains='zee').first()
    if request.method == 'POST':
        form = LifelineResponseForm(request.POST, instance=lifeline_followup)
        print('this is bool of followup lifeline, form.valid ', form.is_valid())
        print(form.errors.as_data())
        if form.is_valid():
            print('this is line 199, lifeline followup form valid bool: ', form.is_valid())
            result = form.save(commit=False)
            result.followup_calls += 1
            # if result.tag == 'Not interested' or result.followup_calls > 2:
            #     result.status = "Spoken To"
            #     result.save()
            #     return redirect('lifelines_for_followup')
            # result.accessed = now
            result.save()
            return redirect('lifelines_for_followup')
    else:
        form = LifelineResponseForm(instance=lifeline_followup)
    return render(request, 'pydb4/lifeline_followup_form.html', {'form': form, 'patient': lifeline_followup})

@login_required
def lifelines_report_general(request):
    # total number in system
    lifelines = Lifeline.objects.all()

    # number of unprocessed lifelines, not called yet
    unprocessed = Lifeline.objects.filter(processed=False).order_by('distance')

    # number of lifelines called so far
    processed = Lifeline.objects.filter(processed=True).order_by('distance')

    # number of explicitly interested patients
    interested = Lifeline.objects.filter(tag='Interested').order_by('distance')

    # number of patients that were left voicemails and can still call again
    voicemails = Lifeline.objects.filter((Q(result="Left (Another) Voicemail") | Q(status="Left Voicemail")) & Q(followup_calls__lte=2)).distinct()

    # number of contacts that requested no further contact
    no_further_contact = Lifeline.objects.filter(Q(tag='Not interested')|Q(result='No Longer Applicable (due to various reasons)')).distinct()

    # number of contacts we have called max amount of times (3 total calls, 1 initial and 2 follow-up), not calling further
    maxed_calls = Lifeline.objects.filter(followup_calls__gte=2)

    # dict = {'lifelines': lifelines, 'unprocessed': unprocessed, 'processed': processed, 'interested': interested, 'voicemails': voicemails, 'no_further_contact': no_further_contact, 'maxed_calls': maxed_calls,}
    return render(request, 'pydb4/lifeline_report_general.html', {'lifelines': lifelines, 'unprocessed': unprocessed, 'processed': processed, 'interested': interested, 'voicemails': voicemails, 'no_further_contact': no_further_contact, 'maxed_calls': maxed_calls,})


@login_required
def generate_po_pdf(request, po_id):
    from docxtpl import DocxTemplate
    from email.message import EmailMessage
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    # Sender's email credentials
    sender_email = "omni.vascular.overflow@gmail.com"
    sender_password = "uhjubjzvjawytfnm"

    # # Recipients' email addresses
    # recipients = [
    #     {"name": "John Doe", "email": "omni.vascular.overflow@gmail.com"},
    #     {"name": "Jane Smith", "email": "office@vasculardoctor.org"},
    # ]

    # # Email content

    # template_html = """
    # <html>
    # <body>
    #     <h1>Hello {name}!</h1>
    #     <p>This is a test email sent using a Python script.</p>
    # </body>
    # </html>
    # """
    doc = DocxTemplate(r"/home/omnivascular/pydb4/pydb/pydb4/initial_edits_Omni_PO_Vendor_Copy.docx")


    fields = [
        "order_date",
        "vendor",
        "po_number",
        "account_number",
        "i_1_#",
        "i_1_descr",
        "i_1_qty",
        "i_2_#",
        "i_2_descr",
        "i_2_qty",
        "i_3_#",
        "i_3_descr",
        "i_3_qty",
        "i_4_#",
        "i_4_descr",
        "i_4_qty",
        "i_5_#",
        "i_5_descr",
        "i_5_qty",
        "i_6_#",
        "i_6_descr",
        "i_6_qty",
        "i_7_#",
        "i_7_descr",
        "i_7_qty",
        "i_8_#",
        "i_8_descr",
        "i_8_qty",
        "i_9_#",
        "i_9_descr",
        "i_9_qty",
        "i_10_#",
        "i_10_descr",
        "i_10_qty",
        "i_11_#",
        "i_11_descr",
        "i_11_qty",
        "i_12_#",
        "i_12_descr",
        "i_12_qty",
        "total",
    ]

    po = PurchaseOrder.objects.get(id=po_id)
    subject = f"DOCX File for Purchase Order #{po.po_number}"
    po_items_qs = po.po_items.all()
    num_po_items = po.po_items.all().count()
    if num_po_items > 1:
        item_range = range(1, num_po_items + 1)
    elif num_po_items == 1:
        item_range = range(1, 2)
    items_dicts = {}
    for i, x in zip(item_range, po_items_qs):
        a = {f"i_{i}": i, f"i_{i}_descr": x.name, f"i_{i}_qty": x.qty_ordered}
        items_dicts = items_dicts | a
    params = {
        "order_date": f"{po.po_date}",
        "vendor": f"{po.vendor}",
        "po_number": f"{po.po_number}",
        "account_number": f"{po.vendor.account_number}",
    }
    params = params | items_dicts
    TOTAL =  {"TOTAL": po_items_qs.aggregate(Sum("qty_ordered"))['qty_ordered__sum']}
    params = params | TOTAL
    # context = {k: v for k in fields for v in range(0, len(fields))}
    doc.render(context=params)
    now = datetime.now().strftime("%m_%d_%Y_%H_%M_%S")
    docx_filename = f"{po.po_number}_Generated_{now}.docx"
    doc.save(docx_filename)
    time.sleep(1)
    msg = EmailMessage()
    msg["From"] = sender_email

    msg["Subject"] = subject
    msg["To"] = ["omni.vascular.overflow@gmail.com", "admin@vasculardoctor.org"]
    msg["Cc"] = "yousaf@omni.aberdeenmedical.org"
    msg.set_content(f"Please find attached a DOCX of Purchase Order #{po.po_number}, generated on: {now}.\nIt can be exported directly to PDF as needed. For any questions, please contact Yousaf for technical assistance.")
    # filename = "img_3.png"
    # filename = (
    #     r"C:\Users\omniv\OneDrive\Documents\py-testing\python_notes_payperiodSystem.pdf"
    # )
    with open(docx_filename, "rb") as file:
        docx = file.read()
    # msg.add_attachment(img, maintype="image", subtype="png")
    msg.add_attachment(
        docx, maintype="application", subtype="docx", filename=docx_filename
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, msg["To"] + msg['CC'], msg.as_string())
        print(f'Email of DOCX sent to recipient, for PO #{po.po_number}')
    messages.success(
        request,
        "DOCX of this Purchase Order generated successfully!",
    )
    po_list = PurchaseOrder.objects.all().order_by("-po_date")
    return render(
        request,
        "pydb4/po_list.html",
        {"po_list": po_list},
    )






@login_required
def lifelines_to_callback(request):
    # patient_list = Lifeline.objects.filter(tag__icontains="Patient Requested Callback", followup_calls__lte=2).exclude(name__icontains='zee')
    # patient_list = Lifeline.objects.filter(tag="Interested", followup_calls__lte=2).exclude(name__icontains='zee')
    removal_criteria_2 = Q(result="No Longer Applicable (due to various reasons)") | Q(followup_calls__gte=3)
    callback_qs = Lifeline.objects.filter(tag="Patient Requested Callback", followup_calls__lte=2).exclude(name__icontains='zee').exclude(removal_criteria_2)
    return render(request, "pydb4/lifeline_callback.html", {"patient_list": callback_qs})

@login_required
def lifelines_callback_form(request):
    # prior = timedelta(days=8)
    # now = datetime.now()
    # removal_criteria = Q(tag__icontains='Not interested') | Q(followup_calls__gte=3) | Q(q3_response__icontains="No") & ~Q(tag__icontains="Patient Requested Callback")
    # lifeline_followup = Lifeline.objects.filter(processed=True, accessed__lte=(now-prior)).exclude(removal_criteria).first()
    # lifeline_callback = Lifeline.objects.filter(tag__icontains="Patient Requested Callback", followup_calls__lte=2).first()
    removal_criteria_2 = Q(result="No Longer Applicable (due to various reasons)") | Q(followup_calls__gte=3)
    callback_qs = Lifeline.objects.filter(tag="Patient Requested Callback", followup_calls__lte=2).exclude(name__icontains='zee').exclude(removal_criteria_2)
    # lifeline_callback = Lifeline.objects.filter(tag="Interested", followup_calls__lte=2).exclude(name__icontains='zee').first()
    lifeline_callback = callback_qs.first()
    if request.method == 'POST':
        form = LifelineResponseForm(request.POST, instance=lifeline_callback)
        print('callback form errors.asdata() = ', form.errors.as_data())
        if form.is_valid():
            result = form.save(commit=False)
            if form.has_changed():
                result.followup_calls += 1
                # if result.tag == 'Not interested' or result.followup_calls > 2:
                #     result.status = "Spoken To"
                #     result.save()
                #     return redirect('lifelines_to_callback')

                result.save()
            return redirect('lifelines_to_callback')
        else:
            messages.error(request,
                    "Error with Callback form submission, please see stack trace and refer to IT admin.",)
    form = LifelineResponseForm(instance=lifeline_callback)
    return render(request, 'pydb4/lifeline_callback_form.html', {'form': form, 'patient': lifeline_callback})


# 11/09/2023: add logic here where request.user also gets passed to procedure update function
@login_required
def database_update_procedures(request):
    with thread_lock:
        try:
            create_procedure_objects_from_sheets_data()
            procedure_list = Procedure.objects.all().order_by("-date_performed")
            messages.success(
                request,
                "Current procedures being updated from Google Sheets, please wait 1-2 minutes before new search.",
            )
            return render(
                request,
                "pydb4/procedure_list.html",
                {"procedure_list": procedure_list},
            )
        except Exception:
            traceback.print_exc()
            messages.error(
                request,
                "Error with updating current procedures, please see stack trace and refer to IT admin.",
            )
            procedure_list = Procedure.objects.all().order_by("-date_performed")
            return render(
                request,
                "pydb4/procedure_list.html",
                {"procedure_list": procedure_list},
            )


@login_required
def database_update_purchaseorders(request):
    with thread_lock:
        try:
            create_po_objects_from_sheets_data(request.user.id)
            po_list = PurchaseOrder.objects.all().order_by("-po_date")
            messages.success(
                request,
                "Current POs being updated from Google Sheets, please wait 1-2 minutes before new search.",
            )
            return render(
                request,
                "pydb4/po_list.html",
                {"po_list": po_list},
            )
        except Exception:
            traceback.print_exc()
            messages.error(
                request,
                "Error with updating current POs, please see stack trace and refer to IT admin.",
            )
            po_list = PurchaseOrder.objects.all().order_by("-po_date")
            return render(
                request,
                "pydb4/po_list.html",
                {"po_list": po_list},
            )


@login_required
def all_procedures(request):
    # insert function call to update procedures based on items used sheet, see utils
    procedure_list = Procedure.objects.all().order_by("-date_performed")
    oldest = Procedure.objects.all().order_by("date_performed").first()
    return render(
        request,
        "pydb4/procedure_list.html",
        {"procedure_list": procedure_list, "oldest": oldest},
    )


@login_required
def all_purchase_orders(request):
    # insert function call to update procedures based on items used sheet, see utils
    po_list = PurchaseOrder.objects.all().order_by("-po_date")
    return render(
        request,
        "pydb4/po_list.html",
        {"po_list": po_list},
    )


@login_required
def all_vendor_products(request, vendor_id):
    print("all_vendor_products view: ", request.META.get("HTTP_X_REQUESTED_WITH"))
    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        products = Product.objects.filter(vendor_id=vendor_id)
        vendor = Vendor.objects.get(id=vendor_id)
        product_data = [{"name": p.name} for p in products]
        vendor_data = {
            "id": vendor.id,
            "name": vendor.name,
            # Can add any other desired fields
        }
        response_data = {
            "products": product_data,
            "vendor": vendor_data,
        }
        # response_json = json.dumps(response_data)
        return JsonResponse(response_data, safe=False)
    else:
        products = Product.objects.filter(vendor_id=vendor_id)
        vendor = Vendor.objects.get(id=vendor_id)
        return render(
            request,
            "pydb4/vendor_products.html",
            {"products": products, "vendor": vendor},
        )


@login_required
def expiry_check_custom_dates(request):
    submitted = False
    if request.method == "POST":
        print(request.POST)
        print("test_widgets: ", request.POST.items())
        start = request.POST["date_start"]
        end = request.POST["date_end"]
        # can add, if start == end logic, so as to say, if less/than/equalto (lte) today, all in range from today till that point)
        products = Product.objects.filter(
            expiry_date__range=(
                recompose_date(start, return_str=False),
                recompose_date(end, return_str=False),
            )
        ).filter(quantity_on_hand__gt=0)
        submitted = True
        # messages.success(request, f"Search results starting from {start} until {end}.", extra_tags='search')
        start_ref = recompose_date(start, db_format=False)
        end_ref = recompose_date(end, db_format=False)
        return render(
            request,
            "pydb4/expiring_products_list.html",
            {
                "product_list": products,
                "submitted": submitted,
                "start": start_ref,
                "end": end_ref,
            },
        )
    form = DateSelectorForm()
    return render(
        request,
        "pydb4/expiry_check_custom.html",
        {"form": form, "submitted": submitted},
    )


@login_required
def product_detail(request, item_id):
    product = Product.objects.get(id=item_id)
    records = sorting_histories(product)
    return render(
        request, "pydb4/product_detail.html", {"product": product, "records": records}
    )


@login_required
def procedure_detail(request, procedure_id):
    procedure = Procedure.objects.get(id=procedure_id)
    products = procedure.products_used.all()
    # --- later can add reference below to context dict, such as details of procedure (who entered it etc)
    # records = AuditLog.objects.filter(Q(object_id=item_id) & Q(field_name="quantity_on_hand")).order_by('-modified_date')
    # for r in records:
    #     print(r.content_object)
    #     print(r.object_id)
    #     print(r.field_name)
    return render(
        request,
        "pydb4/procedure_detail.html",
        {"procedure": procedure, "products": products},
    )


@login_required
def po_detail(request, po_id):
    purchase_order = PurchaseOrder.objects.get(id=po_id)
    po_items = purchase_order.po_items.all()
    total_num_po_items = po_items.aggregate(Sum("qty_ordered"))['qty_ordered__sum']
    return render(
        request, "pydb4/po_detail.html", {"po": purchase_order, "po_items": po_items, "sum_po_items": total_num_po_items,}
    )


@login_required
def product_search(request):
    multiple = ""
    if request.method == "POST":
        print(request.POST)
        searched = request.POST["searched"].strip().lower()
        excluder = False
        target = ''
        if "~" in searched:
            s = searched.split(' ')
            [target] = [w for w in s if '~' in w]
            searched = searched.strip(target).strip()
            target = target.strip('~')
            excluder = True
        print('this is target, excluder', target, excluder)
        if searched and "+ALL" not in searched:
            # products = [s.strip().lower() for s in searched.split("-") if '-' in search else ]
            if "-" in searched and searched.count("-") == 3:
                multiple = "barcode"
                product = [s.strip() for s in searched.split("-")]
                queries = (
                    Q(name__icontains=product[0])
                    & Q(barcode__icontains=product[1])
                    & Q(
                        expiry_date__exact=recompose_date(
                            phrase=product[2], return_str=False
                        )
                    )
                    & Q(lot_number__icontains=product[3])
                )
                search_query = queries
                print('this is for barcode/single:')
                print(search_query)
            else:
                multiple = "single"
                product = [s.strip() for s in searched.split(" ")]
                # recompose_date(phrase=term, return_str=False)
                # db_date_format_alt(term)
                queries = [
                    Q(name__icontains=term)
                    # | Q(size__icontains=term)
                    | Q(barcode__icontains=term)
                    | Q(reference_id__icontains=term)
                    | Q(lot_number__icontains=term)
                    # | Q(expiry_date__exact=recompose_date(phrase=term, return_str=False))
                    for term in product
                ]
                print(queries)
                search_query = construct_and_search_query(queries)
            result = Product.objects.filter(search_query).order_by("expiry_date") if not excluder else Product.objects.filter(search_query).order_by("expiry_date").exclude(name__icontains=target)
            total_quantity_results = result.aggregate(Sum("quantity_on_hand"))
            return render(
                request,
                "pydb4/product_search.html",
                {
                    "searched": product,
                    "products": result,
                    "multiple": multiple,
                    "total_num": total_quantity_results["quantity_on_hand__sum"],
                },
            )
        elif "+ALL" in searched:
            multiple = "multiple"
            products = [s.strip().lower() for s in searched.split(" ")]
            queries = [
                Q(name__icontains=term)
                # | Q(size__icontains=term)
                | Q(reference_id__icontains=term)
                | Q(barcode__icontains=term)
                | Q(lot_number__icontains=term)
                # | Q(expiry_date__exact=recompose_date(phrase=term, return_str=False))
                for term in products
            ]
            search_query = construct_or_search_query(queries)
            results = Product.objects.filter(search_query).order_by("expiry_date") if not excluder else Product.objects.filter(search_query).order_by("expiry_date").exclude(name__icontains=target)
            total_quantity_results = results.aggregate(Sum("quantity_on_hand"))
            return render(
                request,
                "pydb4/product_search.html",
                {
                    "searched": products,
                    "products": results,
                    "multiple": multiple,
                    "total_num": total_quantity_results["quantity_on_hand__sum"],
                },
            )
        else:
            products = Product.objects.filter(
                Q(name__icontains=searched)
                # | Q(size__icontains=searched)
                | Q(reference_id__icontains=searched)
                | Q(barcode__icontains=searched)
                | Q(lot_number__icontains=searched)
                # | Q(expiry_date__exact=recompose_date(phrase=searched, return_str=False))
            ).order_by("expiry_date") if not excluder else Product.objects.filter(
                Q(name__icontains=searched)
                # | Q(size__icontains=searched)
                | Q(reference_id__icontains=searched)
                | Q(barcode__icontains=searched)
                | Q(lot_number__icontains=searched)
                # | Q(expiry_date__exact=recompose_date(phrase=searched, return_str=False))
            ).order_by("expiry_date").exclude(name__icontains=target)
            total_quantity_results = products.aggregate(Sum("quantity_on_hand"))
            messages.success(request, "Search completed!", extra_tags="search")
            return render(
                request,
                "pydb4/product_search.html",
                {
                    "searched": searched,
                    "products": products,
                    "multiple": multiple,
                    "total_num": total_quantity_results["quantity_on_hand__sum"],
                },
            )
    else:
        return render(request, "pydb4/product_list.html", {})


@login_required
def update_product(request, product_id):
    product = Product.objects.get(pk=product_id)
    print("product instance info: ", product.last_modified, product.quantity_on_hand)
    if not product.last_modified:
        product.last_modified = datetime(1900, 1, 1)
    updated = False
    readonly_fields = ["name", "reference_id", "size", "expiry_date", "vendor"]
    # readonly_fields = ['name', 'reference_id', 'expiry_date', 'vendor']
    if request.method == "POST":
        print("dict and items here:", list(request.POST.items()))
        print(
            "POST form instance info: ",
            request.POST.get("last_modified"),
            request.POST.get("quantity_on_hand"),
        )
        form = ProductForm(
            request.POST, instance=product, readonly_fields=readonly_fields
        )
        # for field in readonly_fields:
        #     form.fields[field].initial = getattr(product, field)
        #     form.fields[field].widget.attrs['readonly'] = True
        if form.is_valid():
            result = form.save(commit=False)
            try:
                result.employee = request.user
            except Exception:
                traceback.print_exc()
            print(f"For updating {product.name}, User ID: {request.user.id}")
            update_product_in_sheets(
                result.quantity_on_hand,
                result.reference_id,
                result.lot_number,
                result.expiry_date,
            )
            now = datetime.now(tz=pytz.timezone("US/Eastern"))
            if product.quantity_on_hand != request.POST.get(
                "quantity_on_hand"
            ) or product.is_purchased != request.POST.get("is_purchased") or product.notes != request.POST.get("notes"):
            #   or product.notes != request.POST.get("notes", ''):
                result.last_modified = now
            else:
                result.last_modified = product.last_modified
            # result.notes = product.notes.append(f'{result.notes}')
            print(type(result.notes))
            result.save()
            updated = True
            redirect_url = reverse("product_detail", args=[product_id])
            if updated:
                redirect_url += "?redirect_flag=true"
            print(result.employee.username)
            redirect_url += f"?user={result.employee.username}"
            return HttpResponseRedirect(redirect_url)
        else:
            print(form.errors)
            messages.error(
                request,
                f"Form unable to be saved, please contact IT admin. {form.errors}",
            )
    else:
        form = ProductForm(instance=product, readonly_fields=readonly_fields)
    return render(
        request,
        "pydb4/update_product.html",
        {"product": product, "form": form, "readonly_fields": readonly_fields},
    )


@login_required
def update_po(request, po_id):
    from django.forms import modelformset_factory

    po = PurchaseOrder.objects.get(pk=po_id)
    POItemFormSet = modelformset_factory(PO_Item, form=POItemForm, extra=0)
    print("purchase order instance info: ", po.last_modified, len(po.po_items.all()))
    updated = False
    readonly_fields = ["vendor", "po_date"]
    # readonly_fields = ['name', 'reference_id', 'expiry_date', 'vendor']
    print("dict and items here:", request.POST.items())
    if request.method == "POST":
        form = PurchaseOrderForm(
            request.POST, instance=po, readonly_fields=readonly_fields
        )
        po_item_formset = POItemFormSet(request.POST, queryset=po.po_items.all())
        print("this is dict of form:", list(form))
        print("this is dict of formset:", list(po_item_formset))
        # form.status = po.status
        # for field in readonly_fields:
        #     form.fields[field].initial = getattr(product, field)
        #     form.fields[field].widget.attrs['readonly'] = True
        print(dict(request.POST))
        print(
            form.is_valid(),
            " is form.is_valid(), this is po item formset valid boolean: ",
            po_item_formset.is_valid(),
        )
        if form.is_valid():
            result_po = form.save(commit=False)
            if po_item_formset.is_valid():
                result_po_item_formset = po_item_formset.save()
            else:
                print(po_item_formset.errors)
                print(po_item_formset)
            # for po_item_form in po_item_formset:
            #     print('po item form valid? for', po_item_form)
            #     if po_item_form.is_valid():
            #         print('po item form IS valid for', po_item_form)
            #         po_item_form.save()
            try:
                result_po.employee = request.user  # logged in user
            except Exception:
                traceback.print_exc()
            now = datetime.now(tz=pytz.timezone("US/Eastern"))
            result_po.last_modified = now
            result_po.save()
            po_item_formset.save()
            po_updated = PurchaseOrder.objects.get(id=result_po.id)
            for item in po_updated.po_items.all():
                item.notes += [((len(item.notes) + 1), now.strftime("%m-%d-%Y"))]
                item.save()
            updated = True
            redirect_url = reverse("po_detail", args=[po_id])
            if updated:
                redirect_url += "?redirect_flag=true"
            print(result_po.employee.username)
            redirect_url += f"?user={result_po.employee.username}"
            return HttpResponseRedirect(redirect_url)
        else:
            print(form.errors)
            messages.error(
                request,
                f"{po_item_formset.errors}Form unable to be saved, please contact IT admin. {po_item_formset.errors}\n---{form.is_valid()}\n -- poitemformset{po_item_formset.is_valid()}--{form.status}----{form.non_field_errors}",
            )
    else:
        form = PurchaseOrderForm(instance=po, po_id=po_id)
        po_item_formset = POItemFormSet(queryset=po.po_items.all())
    return render(
        request,
        "pydb4/update_po.html",
        {
            "po": po,
            "form": form,
            "po_item_formset": po_item_formset,
            "readonly_fields": readonly_fields,
        },
    )


@login_required
def report_items_added_30days(request):
    data_df = get_data_from_api(
        ["New Items for Inventory FORM", False]
    )  # this gathers df of items new
    data_df_processed = items_added_30days(data_df)
    items_dict = data_df_processed.to_dict(orient="records")
    # above is a list of dict objects that represent data from sheets file reflecting items added last 30 days,
    # can also check this versus database, match items, and then pass those products (as QuerySet dict) to context object
    # ---- add this line to reports-items-added html template, to get link for each item, once their records match
    #         <strong><a href="{% url 'product_detail' p.id %}">{{p.name}}</a></strong>
    # so that it could be easier to define properly in the html template
    # for item in items_dict:
    #     check = Product.objects.filter(ref_id_lot_number_expiry_date__icontains=item['ref_id_lot_number_expiry_date'])
    #     if check.exists():
    #         item['id'] = check.first().id
    #         print('added ID for this item to items_dict:', item['name'])
    product_list = items_dict
    return render(
        request,
        "pydb4/products_added_30days_report.html",
        {"product_list": product_list},
    )


@login_required
# mirror of above, if comments needed
def report_items_used_30days(request):
    data_df = get_data_from_api(
        ["Items Used in Procedure FORM", False]
    )  # this gathers df of items used
    data_df_processed = items_used_30days(data_df)
    # list of attributes to add as columns, these are absent from the items used sheet
    attributes_to_add = [
        "name",
        "reference_id",
        "id",
        "expiry_date",
        "quantity_on_hand",
        "vendor",
        "size",
        "lot_number",
    ]
    barcode_list = data_df_processed["barcode"]
    # dictionary to collect attribute data for each barcode
    data_dict = {}
    for barcode in barcode_list:
        barcode = str(barcode).strip()
        objs = Product.objects.filter(
            Q(barcode__icontains=barcode) | Q(qr_code__icontains=barcode)
        )
        # list to store attribute data for each object
        objs_data = []
        for obj in objs:
            # dictionary to store attribute data for this object
            obj_data = {}
            # Collect attribute values for this object
            for attribute in attributes_to_add:
                obj_data[attribute] = getattr(obj, attribute)
            # Add the collected data for this object to the list
            objs_data.append(obj_data)
        # Add the list of attribute data for this barcode to the main data dictionary
        data_dict[barcode] = objs_data
    # Now, data_dict holds lists of attribute data for each barcode (can flatten or keep nested)
    # Flattening the data for each barcode into a single dictionary
    flattened_data_dict = {}
    for barcode, objs_data in data_dict.items():
        # Merge the dictionaries for each object into a single dictionary
        flattened_data_dict[barcode] = {
            k: v for obj_data in objs_data for k, v in obj_data.items()
        }
    # Convert the flattened data dictionary into a DataFrame
    print(flattened_data_dict, "line 320 in items used report")
    additional_data_df = pd.DataFrame.from_dict(flattened_data_dict, orient="index")
    print("this is additional data df:")
    print(additional_data_df)
    data_df_processed = data_df_processed.merge(
        additional_data_df, left_on="barcode", right_index=True
    )
    items_dict = data_df_processed.to_dict(orient="records")
    product_list = items_dict
    return render(
        request,
        "pydb4/products_used_30days_report.html",
        {"product_list": product_list},
    )


@login_required
def expiry_check_products_by_month(request, month_number):
    now = datetime.now(tz=pytz.timezone("US/Eastern"))
    products = Product.objects.filter(quantity_on_hand__gt=0).filter(
        expiry_date__gt=now
    )
    results = []
    for x in products:
        datecheck = x.days_until_expiry
        if month_number == 1:
            if datecheck.years == 0 and datecheck.months <= 1:
                print(x.name, x.size, x.expiry_date.date())
                results.append(x)
        if month_number == 3:
            if datecheck.years == 0 and datecheck.months <= 3 and datecheck.months > 1:
                print(x.name, x.size, x.expiry_date.date())
                results.append(x)
        if month_number == 6:
            if datecheck.years == 0 and datecheck.months <= 6 and datecheck.months > 3:
                print(x.name, x.size, x.expiry_date.date())
                results.append(x)
    return render(
        request,
        "pydb4/expiry_check.html",
        {"results": results, "month_number": month_number},
    )


@login_required
# def verify_products(request):
#     submitted = False
#     if request.method == "POST":
#         print('got to here, line 201 in views.py')
#         pattern = r"\r\n|\n|,"  # Regular expression pattern to match "\r\n" or "\n"
#         barcodes_used = re.split(pattern, request.POST.get('products_used', ''))
#         queries = [Q(barcode__icontains=term) for term in barcodes_used if term != '']
#         search_query = construct_or_search_query(queries)
#         results = Product.objects.filter(search_query).order_by('expiry_date')

#     print('got to here, line 209 in views.py')
#     return HttpResponseNotAllowed(['POST'])


@login_required
def extract_objects_using_qr_code(qr_codes_used):
    queries = []
    # Construct individual Q objects for each term
    for term in qr_codes_used:
        date_obj = parser.parse(term.split("-")[2]).date()
        # Construct your Q objects for this term
        q_obj = Q(qr_code__icontains=term) | (
            Q(expiry_date=date_obj)
            & Q(name__icontains=term.split("-")[0])
            & Q(barcode__icontains=term.split("-")[1])
        )
        queries.append(q_obj)
    # Combine all the Q objects using logical OR
    search_query = Q()
    for query in queries:
        search_query |= query
    # Query the database
    results = Product.objects.filter(search_query).order_by("expiry_date")
    return results


@login_required
def procedure(request):
    submitted = False
    if request.method == "POST":
        print("POST here")
        form = ProcedureForm(request.POST)
        qr_codes_used = [
            s.strip()
            for s in request.POST.get("qr_codes_used").split("&")
            if s not in ["", None]
        ]
        queries = []
        # Construct individual Q objects for each term
        for term in qr_codes_used:
            date_obj = parser.parse(term.split("-")[2]).date()
            # this is looking either for precise qr_code match OR all matches for expiry+name+barcode together in one item
            q_obj = Q(qr_code__icontains=term) | (
                Q(expiry_date=date_obj)
                & Q(name__icontains=term.split("-")[0])
                & Q(barcode__icontains=term.split("-")[1])
            )
            queries.append(q_obj)
        # Combine all the Q objects using logical OR
        search_query = Q()
        for query in queries:
            search_query |= query
        results = Product.objects.filter(search_query).order_by("expiry_date")
        if results.first() is None:
            form = ProcedureForm()
            messages.error(
                request,
                "Incorrect data entered for products used, please submit procedure with corrected information.",
            )
            return render(
                request,
                "pydb4/procedure_event.html",
                {"form": form, "submitted": submitted},
            )
        # print('length of results queryset:')
        print("len of results", len(results))
        print(results)
        print(".items: ", request.POST.items)
        # print('original products used field: ', qr_codes_used)
        # print('processed products used field', products_used)
        print("patient_mrn: ", request.POST.get("patient_mrn"))
        print("procedure: ", request.POST.get("procedure"))
        if form.is_valid():
            print(type(form), "the form is valid\n:", form)
            procedure = form.save(commit=False)
            try:
                print("For adding procedure, User ID: ", request.user.id)
                procedure.employee = request.user  # logged in user
                procedure.qr_codes_used = qr_codes_used
                if results:
                    print("showing len, type, and results object itself:")
                    print(len(results), type(results), results)
                    for r in results:
                        print(
                            f"Removing one of this item from inventory: {r.name}-{r.expiry_date}"
                        )
                        print(f"Old quant: {r.quantity_on_hand}")
                        # r.quantity_on_hand -= 1
                        # ---- uncomment above when ready to have add procedure to remove an item from inventory ---
                        # print(f"New quant: {r.quantity_on_hand} ---temporarily disabled, see views.procedure")
                        # r.save()
                        print(f"added {r} to Procedure object, then to be saved")
                procedure.save()
                procedure.products_used.add(*results)
                # for r in results:
                #     procedure.products_used.add(r) # changed to ManyToMany field in model of Procedure
            except:
                traceback.print_exc()
            submitted = True
            return render(
                request,
                "pydb4/procedure_detail.html",
                {"procedure": procedure, "submitted": submitted, "products": results},
            )
        else:
            # print(form.is_valid()) # returns boolean
            print(form.errors)
            print("sorry form not correct, try again.")
            form = ProcedureForm()
            return render(
                request,
                "pydb4/procedure_event.html",
                {"form": form, "submitted": submitted},
            )
    else:
        form = ProcedureForm()
        print("GET here")
        return render(
            request,
            "pydb4/procedure_event.html",
            {"form": form, "submitted": submitted},
        )


@login_required
def create_po(request):
    submitted = False
    if request.method == "POST":
        from collections import Counter

        form = PurchaseOrderForm(request.POST)
        print("full request post dict: ", request.POST)
        # print('patient_mrn: ', request.POST.get('patient_mrn'))
        # print('procedure: ', request.POST.get('procedure'))
        extracted_dict = {k: v for k, v in request.POST.items() if "po_item_name" in k or "po_item_qty" in k}
        # print('extracted_dict here: ', extracted_dict)
        key_count_dict = dict(
            Counter(
                x[-1:] for x in extracted_dict.keys() if x and extracted_dict[x] != ""
            )
        )
        po_item_valid_objects = {
            k: v
            for k, v in extracted_dict.items()
            for x, y in key_count_dict.items()
            if x in k and y == 2
        }
        paired_po_items = [
            (x, y)
            for i_x, x in enumerate(po_item_valid_objects.values())
            for i_y, y in enumerate(po_item_valid_objects.values())
            if i_y == 1 + i_x and i_x % 2 == 0
        ]
        form.status = "PO Created"
        if form.is_valid():
            purchase_order = form.save(commit=False)
            # item_formset.save()
            try:
                print("For creating new PO, User ID: ", request.user.id)
                purchase_order.employee = request.user  # logged in user
                # purchase_order.notes += ["form"]
                purchase_order.save()
                all_po_items = []
                for po_item in paired_po_items:
                    item = PO_Item(name=po_item[0], qty_ordered=po_item[1])
                    item.save()
                    all_po_items.append(item)
            except:
                traceback.print_exc()
            purchase_order.po_items.add(*all_po_items)
            purchase_order.save()
            submitted = True
            messages.success(request, "Purchase order created successfully.")
            # po_items = purchase_order.po_items.all() # 05/21/2024: don't need this, just pass list of PO Item objects should work
            # request, "pydb4/po_detail.html", {"po": purchase_order, "po_items": po_items}
            return render(
                request,
                "pydb4/po_detail.html",
                {"po": purchase_order, "po_items": all_po_items, "submitted": submitted},
            )
        else:
            print(form.errors)
            print("sorry form not correct, try again.")
            messages.error(
                request, "Purchase order form not correct, please try again..."
            )
            form = PurchaseOrderForm()
            return render(
                request,
                "pydb4/create_po.html",
                {"form": form, "submitted": submitted},
            )
    form = PurchaseOrderForm()
    return render(
        request, "pydb4/create_po.html", {"form": form, "submitted": submitted}
    )


@login_required
def add_product(request):
    submitted = False
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            # venue = form.save(commit=False)
            # venue.owner = request.user.id # logged in user
            # venue.save()
            product = form.save(commit=False)
            try:
                print("For adding product, User ID: ", request.user.id)
                product.employee = (
                    request.user
                )  # User.objects.get(pk=request.user.id) #logged in user
                # product.employee = request.user.id
                now = datetime.now(tz=pytz.timezone("US/Eastern"))
                product.last_modified = now
                product.save()
                add_product_to_sheets(
                    quantity=product.quantity_on_hand,
                    vendor=product.vendor.name,
                    product_name=product.name,
                    product_size=product.size,
                    expiry_date=recompose_date(product.expiry_date, db_format=False),
                    reference_id=product.reference_id,
                    lot_number=product.lot_number,
                    barcode=product.barcode,
                )
            except:
                traceback.print_exc()
            submitted = True
            messages.success(request, "Product added successfully.")
            # return  render('/add_product?submitted=True')
            print(type(product))
            return render(
                request,
                "pydb4/product_detail.html",
                {"product": product, "submitted": submitted},
            )
    else:
        form = ProductForm()
        if "submitted" in request.GET:
            submitted = True
        return render(
            request, "pydb4/add_product.html", {"form": form, "submitted": submitted}
        )


@login_required
def add_vendor(request):
    submitted = False
    if request.method == "POST":
        form = VendorForm(request.POST)
        vendors = Vendor.objects.filter(
            id=request.POST.get("id"),
            name=request.POST.get("name"),
            abbrev=request.POST.get("abbrev"),
        )
        if not vendors.exists():
            if form.is_valid():
                try:
                    vendor = form.save(commit=False)
                    print("Adding new vendor, Vendor ID: ", vendor.id)
                    vendor.employee = User.objects.get(
                        pk=request.user.id
                    )  # logged in user
                    vendor.save()
                    messages.success(request, "Vendor added successfully.")
                    submitted = True
                    products = Product.objects.filter(vendor_id=vendor.id)
                    return render(
                        request,
                        "pydb4/vendor_products.html",
                        {
                            "vendor": vendor,
                            "submitted": submitted,
                            "products": products,
                        },
                    )
                except Exception as e:
                    traceback.print_exc()
                    print("An error occurred:", str(e))
                    return HttpResponse(
                        "An error occurred while adding the vendor. Please try again later."
                    )
            else:
                # Handle form validation errors here
                print("Form errors here:", form.errors)
                messages.error(
                    request,
                    "Form validation failed. Please check the data you entered: \n All Vendor information must be unique (ID, Name, Abbreviation).",
                )
                vendor_list = Vendor.objects.all()
                return render(
                    request,
                    "pydb4/vendor_list.html",
                    {"vendor_list": vendor_list},
                )
        else:
            vendor = vendors.first()
            messages.error(request, "Vendor already exists in records.")
            products = Product.objects.filter(vendor_id=vendor.id)
            return HttpResponseRedirect(
                reverse("all-vendor-products", args=[vendor.id])
            )  # Redirect to vendor detail page
    else:
        form = VendorForm()
        if "submitted" in request.GET:
            submitted = True
        return render(
            request, "pydb4/add_vendor.html", {"form": form, "submitted": submitted}
        )


@login_required
def home(request):
    return render(
        request,
        "pydb4/home.html",
        {},
    )
