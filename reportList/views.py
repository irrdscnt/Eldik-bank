from django.shortcuts import render
from reportList.models import *
import random
import string
from authorization.models import User
from core.models import *
from core_requests.models import *
from reportList.models import *


def generate_unique_document_number():
    while True:
        doc_number = ''.join(random.choices(string.digits, k=10))
        if not DocumentNumber.objects(document_number=doc_number).first():
            DocumentNumber(document_number=doc_number).save()
            return doc_number


def generate_waybill(request):
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    car_id = request.GET.get('car_id')

    if not all([from_date, to_date, car_id]):
        return HttpResponse("Missing required parameters: from_date, to_date, car_id", status=400)

    try:
        from_date = datetime.strptime(from_date, '%Y-%m-%d')
        to_date = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        return HttpResponse("Invalid date format. Use YYYY-MM-DD", status=400)

    try:
        car_id = int(car_id)
        car = Car.objects(id_car=car_id).first()
        if not car:
            return HttpResponse(f"Car with id_car {car_id} not found", status=404)
    except ValueError:
        return HttpResponse("Invalid car_id: must be an integer", status=400)

    doc_number = generate_unique_document_number()

    car_users = Car_user.objects(car=car, created_at__gte=from_date, created_at__lte=to_date)
    drivers = [car_user.user for car_user in car_users if car_user.user]

    requests = Request.objects(
        driver__in=[driver.id for driver in drivers],
        date__gte=from_date,
        date__lte=to_date
    ).order_by('date')

    trips = []
    for req in requests:
        for route in req.routes:
            odometer = OdometerReading.objects(request=req, routes=route).first()
            mileage = (
                    odometer.end_odometer - odometer.start_odometer) if odometer and odometer.start_odometer and odometer.end_odometer else 0
            trips.append({
                'route_id': str(route.id),
                'departure': route.departure or '',
                'destination': route.destination or '',
                'start_time': route.start_time.strftime('%H:%M') if route.start_time else '',
                'end_time': route.end_time.strftime('%H:%M') if route.end_time else '',
                'mileage': mileage,
                'start_hour': route.start_time.strftime('%H') if route.start_time else '',
                'start_minute': route.start_time.strftime('%M') if route.start_time else '',
                'end_hour': route.end_time.strftime('%H') if route.end_time else '',
                'end_minute': route.end_time.strftime('%M') if route.end_time else '',
            })

    return render(request, '../templates/path_list.html', {
        'doc_number': doc_number,
        'car': car,
        'from_date': from_date.strftime('%d'),
        'to_date': to_date.strftime('%d'),
        'month': from_date.strftime('%m'),
        'year': from_date.strftime('%Y'),
        'drivers': drivers,
        'trips': trips
    })


def generate_route_sheet(request):
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    car_id = request.GET.get('car_id')
    waybill_number = request.GET.get('waybill_number')
    extended_to = request.GET.get('extended_to')

    if not all([from_date, to_date, car_id, waybill_number]):
        return HttpResponse("Missing required parameters: from_date, to_date, car_id, waybill_number", status=400)

    try:
        from_date = datetime.strptime(from_date, '%Y-%m-%d')
        to_date = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        return HttpResponse("Invalid date format for from_date or to_date. Use YYYY-MM-DD", status=400)

    try:
        car_id = int(car_id)
        car = Car.objects(id_car=car_id).first()
        if not car:
            return HttpResponse(f"Car with id_car {car_id} not found", status=404)
    except ValueError:
        return HttpResponse("Invalid car_id: must be an integer", status=400)

    extended_day = extended_month = extended_year = ''
    if extended_to:
        try:
            extended_date = datetime.strptime(extended_to, '%Y-%m-%d')
            extended_day = extended_date.strftime('%d')
            extended_month = extended_date.strftime('%m')
            extended_year = extended_date.strftime('%Y')
        except ValueError:
            return HttpResponse("Invalid extended_to date format. Use YYYY-MM-DD", status=400)

    odometer_readings = OdometerReading.objects(
        car=car,
        created_at__gte=from_date,
        created_at__lte=to_date
    ).order_by('created_at')

    request_ids = [odometer.request.id for odometer in odometer_readings if odometer.request]

    requests = Request.objects(
        id__in=request_ids,
        date__gte=from_date,
        date__lte=to_date
    ).order_by('date')

    first_reading = odometer_readings.order_by('created_at').first()
    last_reading = odometer_readings.order_by('-created_at').first()
    start_odometer = first_reading.start_odometer if first_reading and first_reading.start_odometer is not None else 0
    end_odometer = last_reading.end_odometer if last_reading and last_reading.end_odometer is not None else 0
    total_mileage = abs(end_odometer - start_odometer) if start_odometer and end_odometer else 0

    trips = []
    for idx, req in enumerate(requests, 1):
        for route in req.routes:
            odometer = OdometerReading.objects(request=req, routes=route, car=car).first()
            mileage = abs(
                odometer.end_odometer - odometer.start_odometer) if odometer and odometer.start_odometer is not None and odometer.end_odometer is not None else 0
            user = req.user
            trips.append({
                'number': idx,
                'subdepartment': user.subdepartment or '' if user else '',
                'route': f"{route.departure or ''} - {route.destination or ''}",
                'start_time': route.start_time.strftime('%H:%M') if route.start_time else '',
                'end_time': route.end_time.strftime('%H:%M') if route.end_time else '',
                'mileage': mileage,
                'user_name': user.name or '' if user else ''
            })

    rows_per_page = 30
    paginated_trips = [trips[i:i + rows_per_page] for i in range(0, len(trips), rows_per_page)]

    return render(request, '../templates/itinerary_list.html', {
        'route_sheet_number': car.id_car,
        'waybill_number': waybill_number,
        'car': car,
        'from_date': from_date.strftime('%d'),
        'to_date': to_date.strftime('%d'),
        'month': from_date.strftime('%m'),
        'year': from_date.strftime('%Y'),
        'extended_day': extended_day,
        'extended_month': extended_month,
        'extended_year': extended_year,
        'start_odometer': start_odometer,
        'end_odometer': end_odometer,
        'total_mileage': total_mileage,
        'paginated_trips': paginated_trips
    })
