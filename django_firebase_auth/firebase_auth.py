"""
Handle the authentication of the user.
Using google authentication (with application)
Using firebase authentication (with web)
"""
import datetime

import firebase_admin.auth
import httplib2
from django.conf.global_settings import DEBUG
from django.contrib.auth.models import User
from django.utils import timezone
from google.auth import jwt
from google.oauth2.id_token import verify_oauth2_token
from google_auth_httplib2 import Request
from rest_framework import authentication, status
from rest_framework.exceptions import APIException

from django_firebase_auth.models import UserFirebaseProfile


class NoAuthToken(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "No authentication token provided"
    default_code = "no_auth_token"


class InvalidAuthToken(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid authentication token provided"
    default_code = "invalid_token"


class TokenExpired(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authorization token is expired"
    default_code = "token_expired"


class FirebaseError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = (
        "The user provided with the auth token is not a "
        "valid Firebase user, it has no Firebase UID"
    )
    default_code = "no_firebase_uid"


def auth_with_firebase(id_token):
    try:
        decoded_token = firebase_admin.auth.verify_id_token(id_token)
    except ValueError as e:
        raise InvalidAuthToken() from e
    return decoded_token


def auth_with_application(id_token, decoded_token):
    try:
        decoded_token = verify_oauth2_token(
            id_token,
            request=Request(
                http=httplib2.Http(),
            ),
            audience=decoded_token["aud"],
        )

    except ValueError as e:
        raise InvalidAuthToken() from e
    return decoded_token


class FirebaseAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header:
            return None
        host = request.get_host()
        if (
            host.startswith("localhost")
            and not auth_header.startswith("Bearer ")
            and DEBUG
        ):
            return User.objects.get(username=auth_header), None
        id_token = auth_header.split(" ").pop()
        try:
            decoded_token = jwt.decode(id_token, verify=False)
        except ValueError as e:
            raise InvalidAuthToken() from e
        is_expired = (
            datetime.datetime.fromtimestamp(decoded_token["exp"])
            < datetime.datetime.now()
        )
        if is_expired:
            raise InvalidAuthToken("Authorization token is expired")
        if "firebase" in decoded_token:
            decoded_token = auth_with_firebase(id_token)
        else:
            decoded_token = auth_with_application(id_token, decoded_token)

        if not id_token or not decoded_token:
            return None

        striped_user_name = decoded_token["email"].split("@")[0]
        display_name = decoded_token.get("name", striped_user_name)
        first_name, last_name = self.convert_user_display_name(display_name)
        user: User = User.objects.get_or_create(
            email=decoded_token.get("email"),
            defaults={
                "username": striped_user_name,
                "first_name": first_name,
                "last_name": last_name,
            },
        )[0]
        profile: UserFirebaseProfile = UserFirebaseProfile.objects.get_or_create(
            user=user, uid=decoded_token.get("uid")
        )[0]

        if decoded_token.get("picture"):
            profile.photo_url = decoded_token.get("picture")
        if decoded_token.get("phone_number"):
            profile.phone_number = decoded_token.get("phone_number")
        if decoded_token.get("name"):
            profile.display_name = decoded_token.get("name")
        profile.save()
        user.last_login = timezone.now()
        profile.save()
        user.save(update_fields=["last_login"])

        return user, None

    def convert_user_display_name(self, display_name: str):
        """
        Convert user display name to first name and last name
        :arg:
        display_name(str): user display name
        :return:
        first_name(str): first name of user
        last_name(str): last name of user
        """
        first_name = display_name.split(" ")[0]
        last_name = None
        if len(display_name) > 1:
            last_name = display_name.split(" ")[1]
        return first_name, last_name
