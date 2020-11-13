import unittest

from google_classroom_client import GoogleClassroomClient, GoogleResourceExhaustedError
from test_utils import patch_google_api_http, patch_failed_api_http


############################
#        Unit Tests        #
############################
class GoogleClassroomClientTestCase(unittest.TestCase):

  def setUp(self):
    self.client = GoogleClassroomClient('fake_token')

  @patch_google_api_http("data/discovery.json", "data/course_928586459_students.json")
  def test_students_list_by_course(self):
    course_id = 928586459
    students_list = self.client.get_students_for_course(course_id)
    expected = len(students_list)
    actual = 4
    self.assertEqual(expected, actual)

  @patch_google_api_http("data/discovery.json", "data/courses.json")
  def test_fetch_active_classrooms(self):
    classrooms = self.client.get_courses(hide_archived=True)
    all_active = all(classroom['courseState'] == 'ACTIVE' for classroom in classrooms)
    self.assertTrue(all_active)

  @patch_failed_api_http('data/throttled_error.json', 429)
  def test_google_classroom_resource_exhausted_exception_raised(self):
      with self.assertRaises(GoogleResourceExhaustedError):
          self.client.get_courses()

  @patch_google_api_http("data/discovery.json", "data/courses.json")
  def test_fetch_active_and_archived_classrooms(self):
    all_classrooms = self.client.get_courses(hide_archived=False)
    archived = [classroom for classroom in all_classrooms if classroom['courseState'] == 'ARCHIVED']
    active = [classroom for classroom in all_classrooms if classroom['courseState'] == 'ACTIVE']
    
    self.assertTrue(len(archived) > 1)
    self.assertTrue(len(active) > 1)
  

# Run all the tests.
if __name__ == '__main__':
    unittest.main(verbosity=2)
