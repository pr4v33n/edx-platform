import json
import logging

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from lti.models import Score
from student.models import unique_id_for_user
from mitxmako.shortcuts import render_to_response, render_to_string
log = logging.getLogger(__name__)


# @login_required
# @csrf_exempt
# @require_POST
def grade(request):
    """
    Endpoint view for lti operations.

    TODO: CRUD
    """
    responses = {'content': 'Hello, Valera and Anton!'}
    return render_to_response('lti_test.html', responses)


# def save_scores(user, response):
#     # parse response to user_id, lti_id and etc.
#     try:
#         obj = Score.objects.get(
#             user=user,
#             unique_user_id=unique_id_for_user(user),
#         )
#         obj.score = 1.0

#     except Score.DoesNotExist:
#         obj = Score(
#             user=user,
#         )
#     obj.save()

#     return {}
