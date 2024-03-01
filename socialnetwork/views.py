# Create your views here.
import json
import pdb
from itertools import chain

from django.contrib.auth import authenticate
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from oauth2_provider.views import TokenView
from rest_framework import viewsets, parsers, permissions, generics, status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from . import serializers, perms, dao, signals, paginators
from .models import User, AlumniProfile, Post, Comment, Reaction, Survey, Group, Question, Answer, Image
import requests


class LoginView(APIView):

    def post(self, request, *args, **kwargs):
        authenticate_url = 'http://192.168.1.10:3000/o/token/'
        username = request.data.get('username')
        password = request.data.get('password')
        role = int(request.data.get('role'))
        user = authenticate(username=username, password=password)
        # pdb.set_trace()
        if user and user.role == role:
            data = {
                'username': username,
                'password': password,
                'client_id': request.data.get('client_id'),
                'client_secret': request.data.get('client_secret'),
                'grant_type': request.data.get('grant_type')
            }
            # pdb.set_trace()

            response = requests.post(authenticate_url, data=data)

            if response.status_code == 200:
                access_token = response.json().get('access_token')
                refresh_token = response.json().get('refresh_token')
                return Response(response.json(), status=status.HTTP_200_OK)
        return Response(status=status.HTTP_400_BAD_REQUEST)

#
# class LoginView(TokenView):
#
#     @method_decorator(sensitive_post_parameters("password"))
#     def post(self, request, *args, **kwargs):
#         data = json.loads(request.body.decode("utf-8"))
#         username = data.get("username")
#         password = data.get("password")
#         role = data.get("role")
#         user = authenticate(username=username, password=password)
#         if user and user.role == role:
#             request.POST = request.POST.copy()
#             # pdb.set_trace()
#
#             # Add application credientials
#             request.POST.update({
#                 'username': username,
#                 'password': password,
#                 'client_id': request.data.get('client_id'),
#                 'client_secret': request.data.get('client_secret'),
#                 'grant_type': request.data.get('grant_type')
#             })
#             return super().post(request)
#         return HttpResponse(content="Khong tim thay tai khoan", status=status.HTTP_401_UNAUTHORIZED)
#

class RegisterView(generics.CreateAPIView):
    serializer_class = serializers.UserSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.MultiPartParser]

    def create(self, request, *args, **kwargs):
        if AlumniProfile.objects.filter(student_id=request.data.get('student_id')).exists():
            # If AlumniProfile already exists, raise an error
            return Response({'student_id': 'student_id is existed'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            alumni = AlumniProfile.objects.create(user=user, student_id=request.data.get('student_id'))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ViewSet,
                  generics.UpdateAPIView,
                  generics.DestroyAPIView,
                  generics.RetrieveAPIView):
    queryset = User.objects.filter(is_active=True).all()
    serializer_class = serializers.UserUpdateDetailSerializer
    parser_classes = [parsers.MultiPartParser]
    permission_classes = [permissions.IsAuthenticated()]

    def get_permissions(self):
        if self.action == "forget_password":
            return [permissions.AllowAny()]
        if self.action in ['change_password','destroy', 'list_friends', "add_posts"]:
            return [perms.IsOwner()]
        if self.action in ['add_surveys', 'add_invitations']:
            return [permissions.IsAdminUser()]
        return self.permission_classes

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data, status=status.HTTP_200_OK)

    @action(methods=['get'], url_path='current-user', url_name='current-user', detail=False)
    def current_user(self, request):
        return Response(self.get_serializer(request.user).data, status=status.HTTP_200_OK)

    @action(methods=['post'], url_path='change_password', detail=True)
    def change_password(self, request, pk):
        password_serializer = serializers.PasswordSerializer(data=request.data)
        # pdb.set_trace()
        if password_serializer.is_valid():
            if not request.user.check_password(password_serializer.data.get('old_password')):
                return Response({'message': 'Incorrect old password'}, status=status.HTTP_400_BAD_REQUEST)
            # set new password
            request.user.set_password(password_serializer.data.get('new_password'))
            request.user.save()
        return Response({'message': 'Successfully Changed'},status=status.HTTP_200_OK)
    # @action(methods=['POST'], url_path='change_password', detail=True)
    # def change_password(self, request, pk=True):
    #     password_serializer = serializers.PasswordSerializer(data=request.data)
    #     pdb.set_trace()
    #     if password_serializer.is_valid():
    #         old_password = password_serializer.validated_data.get('old_password')
    #         new_password = password_serializer.validated_data.get('new_password')
    #
    #         if request.user.check_password(old_password):
    #             request.user.set_password(new_password)
    #             request.user.save()
    #             return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)
    #         else:
    #             return Response({'message': 'Old password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)
    #     else:
    #         return Response(password_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], detail=False, url_path='posts')
    def add_posts(self, request):
        post = Post.objects.create(user=request.user, content=request.data.get('content'))
        Image.objects.create(post=post, image=request.data.get('image'))
        # pdb.set_trace()

        return Response(serializers.PostSerializer(post).data, status=status.HTTP_201_CREATED)

    @action(methods=['post'], detail=True, url_path='surveys')
    def add_surveys(self, request, pk):
        survey_data = request.data
        survey_serializer = serializers.SurveySerializer(data=survey_data)
        if survey_serializer.is_valid():
            survey = survey_serializer.save(user=self.get_object())
            return Response(survey_serializer.data, status=status.HTTP_201_CREATED)
        return Response(survey_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], detail=True, url_path='invitations')
    def add_invitations(self, request, pk):
        invitation_data = request.data
        invitation_serializer = serializers.InvitationSerializer(data=invitation_data)
        if invitation_serializer.is_valid():
            invitation = invitation_serializer.save(user=self.get_object())
            return Response(invitation_serializer.data, status=status.HTTP_201_CREATED)
        return Response(invitation_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], detail=True, url_path='add_friend')
    def add_friend(self, request, pk):
        friend_request = self.create_friend_request(sender=request.user, receiver=self.get_object())
        return Response(serializers.FriendShipSerializer(friend_request).data, status=status.HTTP_201_CREATED)

    @action(methods=['GET'], detail=False, url_path='search')
    def search(self, request):
        users = dao.search_people(params=request.GET)

        return Response(serializers.UserInteractionSerializer(users, many=True).data,
                        status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path='list_friends')
    def list_friends(self, request):
        sender = request.user.friendship_requests_sent.filter(is_accepted=True).all()
        receiver = request.user.friendship_requests_received.filter(is_accepted=True).all()

        friends = list(chain(sender, receiver), request)

        return Response(serializers.FriendShipSerializer(friends, many=True, context={'request': request}).data,
                        status=status.HTTP_200_OK)





class PostViewSet(viewsets.ViewSet,
                  generics.ListAPIView,
                  generics.UpdateAPIView,
                  generics.RetrieveAPIView,
                  generics.DestroyAPIView):
    queryset = Post.objects.filter(active=True).all()
    serializer_class = serializers.PostDetailSerializer
    permission_classes = [permissions.IsAuthenticated()]
    pagination_class = paginators.PostPaginator

    def get_permissions(self):
        if self.action in ['update', 'block_comments_post']:
            return [perms.IsOwner()]
        if self.action.__eq__('destroy'):
            return [perms.IsOwner()]
        return self.permission_classes

    def get_queryset(self):
        queries = self.queryset
        userId = self.request.query_params.get('userId')

        if userId:
            user = User.objects.get(pk=userId)
            if user:
                queries = user.post_set.filter(active=True).order_by('-created_date').all()
        return queries

    @action(methods=['get'], detail=True, url_path="details")
    def list_details(self, request, pk):
        posts = self.queryset.filter(id__contains=pk)
        return Response(self.serializer_class(posts, many=True, context={'request': request}).data,
                        status=status.HTTP_200_OK)

    @action(methods=['get'], detail=False, url_path="list-random-posts")
    def list_random_posts(self, request):
        posts = self.get_queryset().order_by('-created_date').all()
        paginator = PageNumberPagination()
        paginator.page_size = 10  # Số bài viết trên mỗi trang
        result_page = paginator.paginate_queryset(posts, request)
        serializer = self.serializer_class(result_page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

        # return Response(self.serializer_class(posts, many=True, context={'request': request}).data,
        #                 status=status.HTTP_200_OK)

    @action(methods=['post'], detail=True, url_path='comments')
    def add_comments(self, request, pk):
        c = Comment.objects.create(user=request.user, post=self.get_object(), content=request.data.get('content'))

        return Response(serializers.CommentSerializer(c).data, status=status.HTTP_201_CREATED)

    @action(methods=['post'], detail=True, url_path='reacts')
    def react_posts(self, request, pk):
        type = int(request.data.get('type'))
        reaction, created = Reaction.objects.get_or_create(user=request.user, post=self.get_object(),
                                                           type=type)

        if not created:
            reaction.active = not reaction.active
            reaction.save()
        # pdb.set_trace()

        return Response(serializers.PostDetailSerializer(self.get_object(), context={'request': request}).data, status=status.HTTP_204_NO_CONTENT)

    @action(methods=['get'], detail=True)
    def list_comments(self, request, pk):
        comments = self.get_object().comment_set.filter(active=True)

        return Response(serializers.CommentSerializer(comments, many=True, context={'request': request}).data,
                        status=status.HTTP_200_OK)

    @action(methods=['get'], detail=True)
    def list_reactions(self, request, pk):
        reactions = self.get_object().reaction_set.filter(active=True)
        return Response(serializers.ReactionSerializer(reactions, many=True, context={'request': request}).data,
                        status=status.HTTP_200_OK)

    @action(methods=['post'], detail=True, url_path='block_comment')
    def block_comments_post(self, request, pk):
        post = self.get_object()
        post.comment_blocked = not post.comment_blocked
        post.save()

        return Response(status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=True)
    def share_post(self, request, pk):
        # # pdb.set_trace()
        # post_shared = Post.objects.create(user=request.user, content=request.data.get('content'),
        #                                   shared_post=self.get_object())
        #
        # return Response(self.serializer_class(post_shared).data, status=status.HTTP_201_CREATED)
        post = self.get_object()
        if post:
            post_shared = Post.objects.create(user=request.user, content=request.data.get('content'),
                                              shared_post=post)
            serializer = self.get_serializer(post_shared)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': 'Post not found'}, status=status.HTTP_404_NOT_FOUND)



class CommentViewSet(viewsets.ViewSet,
                     generics.UpdateAPIView,
                     generics.DestroyAPIView):
    queryset = Comment.objects.filter(active=True).all()
    serializer_class = serializers.CommentSerializer
    permission_classes = [perms.IsOwner]

    def get_permissions(self):
        if self.action.__eq__('destroy'):
            return [perms.IsCommentAuthorOrPostAuthor()]
        return self.permission_classes


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = serializers.GroupSerializer

    def create(self, request, *args, **kwargs):
        group_name = request.data.get('group_name')
        users_data = request.data.get('users', [])

        group = Group.objects.create(name=group_name)

        for user_data in users_data:
            user = User.objects.get(pk=user_data['id'])
            group.users.add(user)

        serializer = self.get_serializer(group)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        users_data = request.data.get('users', [])

        instance.users.clear()

        for user_data in users_data:
            user = User.objects.get(pk=user_data['id'])
            instance.users.add(user)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SurveyViewSet(viewsets.ViewSet,
                    generics.ListAPIView,
                    generics.UpdateAPIView,
                    generics.RetrieveAPIView):
    queryset = Survey.objects.filter(active=True).all()
    serializer_class = serializers.SurveySerializer
    permission_classes = [permissions.IsAdminUser]

    @action(methods=['POST'], detail=True, url_path='questions')
    def add_questions(self, request, pk):
        question = Question.objects.create(survey=self.get_object(), content=request.data.get('content'))

        return Response(serializers.QuestionSerializer(question).data, status=status.HTTP_201_CREATED)


class QuestionViewSet(viewsets.ViewSet,
                      generics.UpdateAPIView,
                      generics.DestroyAPIView):
    queryset = Question.objects.all()
    serializer_class = serializers.QuestionSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(methods=['post'], detail=True, url_path='answers')
    def answers(self, request, pk):
        answer, created = Answer.objects.get_or_create(user=request.user, question=self.get_object(),
                                                       content=request.data.get('content'))

        if created:
            answer.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_201_CREATED)
