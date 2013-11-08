"""Tests for items views."""

import json
import datetime
from pytz import UTC

from contentstore.tests.utils import CourseTestCase
from xmodule.capa_module import CapaDescriptor
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.django import loc_mapper
from xmodule.modulestore.locator import BlockUsageLocator


class ItemTest(CourseTestCase):
    """ Base test class for create, save, and delete """
    def setUp(self):
        super(ItemTest, self).setUp()

        self.unicode_locator = unicode(loc_mapper().translate_location(
            self.course.location.course_id, self.course.location, False, True
        ))

    def get_old_id(self, locator):
        """
        Converts new locator to old id format.
        """
        return loc_mapper().translate_locator_to_location(BlockUsageLocator(locator))

    def get_item_from_modulestore(self, locator, draft=False):
        """
        Get the item referenced by the locator from the modulestore
        """
        if draft:
            return modulestore('draft').get_item(self.get_old_id(locator))
        else:
            return modulestore().get_item(self.get_old_id(locator))

    def response_locator(self, response):
        """
        Get the id from the response payload
        :param response:
        """
        parsed = json.loads(response.content)
        return parsed['locator']

    def create_xblock(self, parent_locator=None, display_name=None, category=None, boilerplate=None):
        data = {
            'parent_locator': self.unicode_locator if parent_locator is None else parent_locator,
            'category': category
        }
        if display_name is not None:
            data['display_name'] = display_name
        if boilerplate is not None:
            data['boilerplate'] = boilerplate
        return self.client.ajax_post('/xblock', json.dumps(data))


class DeleteItem(ItemTest):
    """Tests for '/xblock' DELETE url."""
    def test_delete_static_page(self):
        # Add static tab
        resp = self.create_xblock(category='static_tab')
        self.assertEqual(resp.status_code, 200)

        # Now delete it. There was a bug that the delete was failing (static tabs do not exist in draft modulestore).
        resp_content = json.loads(resp.content)
        resp = self.client.delete(resp_content['update_url'])
        self.assertEqual(resp.status_code, 204)


class TestCreateItem(ItemTest):
    """
    Test the create_item handler thoroughly
    """
    def test_create_nicely(self):
        """
        Try the straightforward use cases
        """
        # create a chapter
        display_name = 'Nicely created'
        resp = self.create_xblock(display_name=display_name, category='chapter')
        self.assertEqual(resp.status_code, 200)

        # get the new item and check its category and display_name
        chap_locator = self.response_locator(resp)
        new_obj = self.get_item_from_modulestore(chap_locator)
        self.assertEqual(new_obj.scope_ids.block_type, 'chapter')
        self.assertEqual(new_obj.display_name, display_name)
        self.assertEqual(new_obj.location.org, self.course.location.org)
        self.assertEqual(new_obj.location.course, self.course.location.course)

        # get the course and ensure it now points to this one
        course = self.get_item_from_modulestore(self.unicode_locator)
        self.assertIn(self.get_old_id(chap_locator).url(), course.children)

        # use default display name
        resp = self.create_xblock(parent_locator=chap_locator, category='vertical')
        self.assertEqual(resp.status_code, 200)

        vert_location = self.response_locator(resp)

        # create problem w/ boilerplate
        template_id = 'multiplechoice.yaml'
        resp = self.create_xblock(parent_locator=vert_location, category='problem', boilerplate=template_id)
        self.assertEqual(resp.status_code, 200)
        prob_location = self.response_locator(resp)
        problem = self.get_item_from_modulestore(prob_location, True)
        # ensure it's draft
        self.assertTrue(problem.is_draft)
        # check against the template
        template = CapaDescriptor.get_template(template_id)
        self.assertEqual(problem.data, template['data'])
        self.assertEqual(problem.display_name, template['metadata']['display_name'])
        self.assertEqual(problem.markdown, template['metadata']['markdown'])

    def test_create_item_negative(self):
        """
        Negative tests for create_item
        """
        # non-existent boilerplate: creates a default
        resp = self.create_xblock(category='problem', boilerplate='nosuchboilerplate.yaml')
        self.assertEqual(resp.status_code, 200)


class TestEditItem(ItemTest):
    """
    Test xblock update.
    """
    def setUp(self):
        """ Creates the test course structure and a couple problems to 'edit'. """
        super(TestEditItem, self).setUp()
        # create a chapter
        display_name = 'chapter created'
        resp = self.create_xblock(display_name=display_name, category='chapter')
        chap_locator = self.response_locator(resp)
        resp = self.create_xblock(parent_locator=chap_locator, category='sequential')
        resp_content = json.loads(resp.content)
        self.seq_locator = self.response_locator(resp)
        self.seq_update_url = resp_content['update_url']

        # create problem w/ boilerplate
        template_id = 'multiplechoice.yaml'
        resp = self.create_xblock(parent_locator=self.seq_locator, category='problem', boilerplate=template_id)
        resp_content = json.loads(resp.content)
        self.problem_locator = self.response_locator(resp)
        self.problem_update_url = resp_content['update_url']

    def test_delete_field(self):
        """
        Sending null in for a field 'deletes' it
        """
        self.client.ajax_post(
            self.problem_update_url,
            data={'metadata': {'rerandomize': 'onreset'}}
        )
        problem = self.get_item_from_modulestore(self.problem_locator, True)
        self.assertEqual(problem.rerandomize, 'onreset')
        self.client.ajax_post(
            self.problem_update_url,
            data={'metadata': {'rerandomize': None}}
        )
        problem = self.get_item_from_modulestore(self.problem_locator, True)
        self.assertEqual(problem.rerandomize, 'never')

    def test_null_field(self):
        """
        Sending null in for a field 'deletes' it
        """
        problem = self.get_item_from_modulestore(self.problem_locator, True)
        self.assertIsNotNone(problem.markdown)
        self.client.ajax_post(
            self.problem_update_url,
            data={'nullout': ['markdown']}
        )
        problem = self.get_item_from_modulestore(self.problem_locator, True)
        self.assertIsNone(problem.markdown)

    def test_date_fields(self):
        """
        Test setting due & start dates on sequential
        """
        sequential = self.get_item_from_modulestore(self.seq_locator)
        self.assertIsNone(sequential.due)
        self.client.ajax_post(
            self.seq_update_url,
            data={'metadata': {'due': '2010-11-22T04:00Z'}}
        )
        sequential = self.get_item_from_modulestore(self.seq_locator)
        self.assertEqual(sequential.due, datetime.datetime(2010, 11, 22, 4, 0, tzinfo=UTC))
        self.client.ajax_post(
            self.seq_update_url,
            data={'metadata': {'start': '2010-09-12T14:00Z'}}
        )
        sequential = self.get_item_from_modulestore(self.seq_locator)
        self.assertEqual(sequential.due, datetime.datetime(2010, 11, 22, 4, 0, tzinfo=UTC))
        self.assertEqual(sequential.start, datetime.datetime(2010, 9, 12, 14, 0, tzinfo=UTC))
