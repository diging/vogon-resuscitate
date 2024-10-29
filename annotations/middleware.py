from django.utils.deprecation import MiddlewareMixin
from annotations.models import RelationSet
from asgiref.sync import async_to_sync, sync_to_async

class CheckRelationSetStatusMiddleware(MiddlewareMixin):
    """
    Middleware to ensure that RelationSets are correctly marked as ready to submit.
    This middleware runs before each request to check and update the status of 
    RelationSets. RelationSets must have one of three statuses:
    
    - 'not_ready': Concepts are not yet resolved or merged.
    - 'ready_to_submit': All concepts are resolved and the RelationSet is ready for submission.
    - 'submitted': This is handled separately in the submission workflow and does not need to 
                   be updated here.
    
    The purpose of this middleware is to automate the readiness check and ensure that 
    RelationSets are always in the correct state before they can be submitted to Quadriga.
    """

    def process_request(self, request):
        """
        This synchronous method is called before each request. We need to run an 
        asynchronous function (`check_and_update_relation_sets`) to perform the status 
        checks. Since Django middleware is synchronous, we use `async_to_sync` to 
        safely call the async function from this synchronous method.
        """
        async_to_sync(self.check_and_update_relation_sets)()

    async def check_and_update_relation_sets(self):
        """
        This is the asynchronous function responsible for checking and updating the 
        statuses of RelationSets. It fetches all RelationSets that need to be checked, 
        and if they meet the readiness criteria (all related concepts are resolved), 
        it updates their status to 'ready_to_submit'. If not, the status remains 'not_ready'.
        """
        # Fetch RelationSets asynchronously, limiting to those with 'not_ready' or 
        # 'ready_to_submit' statuses.
        relation_sets = await sync_to_async(list)(
            RelationSet.objects.filter(status__in=['not_ready', 'ready_to_submit'])
        )

        # Iterate over the RelationSets and update their status if necessary.
        for relation_set in relation_sets:
            # Call the `update_status` method asynchronously to update the RelationSet's status.
            await sync_to_async(relation_set.update_status)()
