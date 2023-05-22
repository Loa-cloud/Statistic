from . import views
from django.urls import path

urlpatterns = [
    path('', views.index, name='home'),
    path('cql_faq', views.cql_faq, name='cql_faq'),
    path('search', views.search, name='search'),
    path('search/<str:text_id>/', views.text, name='text'),
    path('search/statistic', views.get_stat, name='statistic'),
    path('search/error-stats', views.get_error_stats, name='error-stats'),
    path('search/statistic_data', views.statistic_data, name='statistic_data'),
    path('search/correlation_data', views.correlation_data, name='correlation_data'),

    path('search/correlation_data/statistic_data_get_exel', views.statistic_data_get_exel, name='statistic_data_get_exel')
]
