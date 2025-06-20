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
