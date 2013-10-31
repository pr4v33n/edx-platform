import logging

from django.contrib.auth.models import User
from django.db import models


log = logging.getLogger(__name__)


class Score(models.Model):
    """
    This model stores the scores of different users on LTI problems.
    """
    user = models.ForeignKey(User, db_index=True,
                             related_name='lti_scores')

    # The XModule that wants to access this doesn't have access to the real
    # userid.  Save the anonymized version so we can look up by that.
    unique_user_id = models.CharField(max_length=50, db_index=True)
    problem_id = models.CharField(max_length=150, db_index=True)
    score = models.FloatField(db_index=True)
    created = models.DateTimeField(auto_now_add=True)
