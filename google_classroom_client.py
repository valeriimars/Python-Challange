from functools import wraps

import googleapiclient.discovery
import googleapiclient.errors
import httplib2
from oauth2client.client import AccessTokenCredentials, AccessTokenCredentialsError


FAILED_API_REQUEST_RETRIES = 3


class GoogleClassroomClient:
    def __init__(self, access_token, refresh_token):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.allow_refresh = False

    @property
    def http(self):
        credentials = AccessTokenCredentials(self.access_token, 'Newsela')
        return credentials.authorize(httplib2.Http())

    @property
    def service(self):
        """
        The service is the 'root' resource in the API hierarchy, from which
        child resources can be derived. For instance: self.service.courses()
        refers to the courses resource.
        """
        return googleapiclient.discovery.build(
            'classroom', 'v1', http=self.http, cache_discovery=False
        )

    def _handle_api_errors(api_calling_function):

        @wraps(api_calling_function)
        def wrapper(self, *args, **kwargs):
            try:
                try:
                    return api_calling_function(self, *args, **kwargs)
                except AccessTokenCredentialsError:
                    # Cannot refresh the token
                    raise
                    #self.credentials.refresh()
            except AccessTokenCredentialsError as e:
                raise GoogleClassroomClientError(
                    "The user has an access token, but it's not valid.", full=str(e)
                )
            except googleapiclient.errors.HttpError as ex:
                # This feels brittle, but there's no better way to
                # differentiate between a scoping issue and an error returned
                # because the user doesn't actually use Google Classroom.
                content = ex.content.decode()
                if "insufficient authentication scopes" in content:
                    raise GoogleClassroomClientError(
                        "Insufficient authentication scopes.", full=content
                    )
                elif "@NotGoogleAppsUser" in content:
                    raise GoogleClassroomNotInstalledError(
                        "User is not linked to Google Apps for Education.", full=content
                    )
                elif "@ClassroomDisabled" in content:
                    # ClassroomDisabled indicates that the requesting user
                    # does not have access to Classroom.
                    raise GoogleClassroomDisabledError(
                        "Google Classroom is disabled.", full=content
                    )
                elif "@ClassroomApiDisabled" in content:
                    # ClassroomApiDisabled indicates that the requesting user
                    # does not have access to the Classroom API.
                    raise GoogleClassroomApiDisabledError(
                        "Google Classroom API is disabled.", full=content
                    )
                elif ex.resp.status == 429:
                    # RESOURCE_EXHAUSTED error is returned when Google throttles
                    # requests.
                    raise GoogleResourceExhaustedError("Too many requests.")
                else:
                    raise

        return wrapper

    def get_list_response_pages(self, resource, request_args):
        """Get the pages of a paginated response."""
        request = resource.list(**request_args)
        pages_fetched = 0
        while request is not None:
            response = request.execute(
                http=self.http, num_retries=FAILED_API_REQUEST_RETRIES
            )
            yield response
            request = resource.list_next(request, response)
            pages_fetched += 1
            if pages_fetched > 100:
                # 100 pages is plenty. If we ever have to fetch more than
                # that, it's worth investigating why.
                raise GoogleClassroomClientError("Result set is over 100 pages.")

    @_handle_api_errors
    def get_list_response(self, resource, request_args, unwrap):
        """Get a list response with all the pages combined."""
        responses = self.get_list_response_pages(resource, request_args)
        data = [
            object_ for response in responses for object_ in response.get(unwrap, [])
        ]
        return data

    @_handle_api_errors
    def get_object_response(self, resource, request_args):
        request = resource.get(**request_args)
        data = request.execute(http=self.http, num_retries=FAILED_API_REQUEST_RETRIES)
        return data

    def get_courses(self, hide_archived=False):
        courses = self.get_list_response(
            resource=self.service.courses(),
            request_args={'teacherId': 'me'},
            unwrap='courses',
        )
        if hide_archived:
            courses = [c for c in courses if c['courseState'] == 'ACTIVE']
        return courses

    def get_course(self, course_id):
        course = self.get_object_response(
            self.service.courses(), request_args={'id': course_id}
        )
        return course

    def get_students_for_course(self, course_id):
        students = self.get_list_response(
            resource=self.service.courses().students(),
            request_args={'courseId': course_id},
            unwrap='students',
        )
        return students

    def get_user_profile(self):
        user_profile = self.get_object_response(
            self.service.userProfiles(), request_args={'userId': 'me'}
        )
        return user_profile


class GoogleClassroomClientError(Exception):
    """Generic client error."""

    def __init__(self, message, full=None):
        super().__init__(message)
        self.full_details = full


class GoogleClassroomNotInstalledError(GoogleClassroomClientError):
    """User is not configured to use Google Classroom."""

    pass


class GoogleClassroomDisabledError(GoogleClassroomClientError):
    """
    User does not have access to Google Classroom.
    """

    pass


class GoogleClassroomApiDisabledError(GoogleClassroomClientError):
    """
    User does not have access to the Google Classroom API.
    """

    pass


class GoogleResourceExhaustedError(GoogleClassroomClientError):
    """
    The Classroom API returns a RESOURCE_EXHAUSTED (HTTP 429) error
    when the requested action is not permitted
    because some resource is exhausted (quota, server capacity, etc.).
    """
    pass
