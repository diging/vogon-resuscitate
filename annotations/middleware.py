from django.utils.deprecation import MiddlewareMixin
from annotations.models import RelationSet
from asgiref.sync import async_to_sync, sync_to_async

class CheckRelationSetStatusMiddleware(MiddlewareMixin):
    def process_request(self, request):
        """
        Synchronous middleware that checks and updates the status of RelationSets.
        We call the async function using `async_to_sync`.
        """
        async_to_sync(self.check_and_update_relation_sets)()

    async def check_and_update_relation_sets(self):
        """
        Asynchronous function to check and update RelationSet statuses.
        It ensures the RelationSets are ready to submit if all concepts are resolved.
        """
        # Fetch all RelationSets that need a status check asynchronously
        relation_sets = await sync_to_async(list)(
            RelationSet.objects.filter(status__in=['not_ready', 'ready_to_submit'])
        )

        # Check and update status for each RelationSet
        for relation_set in relation_sets:
            await sync_to_async(relation_set.update_status)()
