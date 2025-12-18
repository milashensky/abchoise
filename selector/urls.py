from django.urls import path
from selector import views

urlpatterns = [
    path('', views.main_view, name='main'),
    path('disabled/', views.disabled_view, name='disabled'),
    path('complete/', views.complete_view, name='complete'),
    path('select/', views.select_view, name='select'),
    path('submit-manual/', views.submit_manual_view, name='submit_manual'),
    path('neither/', views.neither_view, name='neither'),
]
