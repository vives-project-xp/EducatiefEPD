from django.contrib import admin

from .models import BasisCasus, BasisCasusData, FictievePatient, StudentUitwerking, StudentUitwerkingData, User

admin.site.register(User)
admin.site.register(FictievePatient)
admin.site.register(BasisCasus)
admin.site.register(BasisCasusData)
admin.site.register(StudentUitwerking)
admin.site.register(StudentUitwerkingData)
