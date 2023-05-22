from django_filters import rest_framework as filters, DateFromToRangeFilter
from sql.models import Users, Instance, SqlWorkflowContent, WorkflowAudit, SqlWorkflow,ResourceGroup


class UserFilter(filters.FilterSet):
    class Meta:
        model = Users
        fields = {
            "id": ["exact"],
            "username": ["exact"],
        }


class InstanceFilter(filters.FilterSet):
    class Meta:
        model = Instance
        fields = {
            "id": ["exact"],
            "instance_name": ["icontains"],
            "db_type": ["exact"],
            "host": ["exact"],
            "resource_group__group_name": ["exact"],
        }


class ResourceGroupFilter(filters.FilterSet):
    class Meta:
        model = ResourceGroup
        fields = {
            "group_id": ["exact"],
            "group_name": ["icontains"],
        }


class WorkflowFilter(filters.FilterSet):
    class Meta:
        model = SqlWorkflowContent
        fields = {
            "id": ["exact"],
            "workflow_id": ["exact"],
            "workflow__instance__instance_name": ["exact"],
            "workflow__workflow_name": ["icontains"],
            "workflow__instance_id": ["exact"],
            "workflow__group_name": ["exact"],
            "workflow__db_name": ["exact"],
            "workflow__engineer": ["exact"],
            "workflow__status": ["exact"],
            "workflow__create_time": ["lt", "gte"],
        }


class WorkflowAuditFilter(filters.FilterSet):
    class Meta:
        model = WorkflowAudit
        fields = {
            "workflow_title": ["icontains"],
            "workflow_type": ["exact"],
        }


class SqlWorkflowFilter(filters.FilterSet):
    create_time = DateFromToRangeFilter()

    class Meta:
        model = SqlWorkflow
        fields = ["create_time", "status", "instance_id", "group_id"]
