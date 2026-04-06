import os, django, re
os.environ['DJANGO_SETTINGS_MODULE'] = 'project.settings'
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
u = get_user_model().objects.filter(is_superuser=True).first()
c = Client()
c.force_login(u)

# Simulate exact form submission: empty dates + search term
r = c.get('/admin/management/entry/', {'date__gte': '', 'date__lte': '', 'q': 'Shavin'}, SERVER_NAME='127.0.0.1')
html = r.content.decode('utf-8', 'ignore')
qs = r.request.get('QUERY_STRING', '')
print('Query string submitted:', qs)
print('Final URL path:', r.request.get('PATH_INFO'))
print('Status:', r.status_code)
counts = re.findall(r'(\d+) result', html)
print('Results found:', counts)
err_flag = 'e=1' in qs or '?e=1' in html
print('Error flag e=1 present:', err_flag)
print('PASS' if counts and not err_flag else 'FAIL')
