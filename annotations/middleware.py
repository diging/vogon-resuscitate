from django.utils.deprecation import MiddlewareMixin
from annotations.models import RelationSet
from asgiref.sync import async_to_sync, sync_to_async
from django.utils import timezone
from datetime import timedelta

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

    # Cache the last check time to reduce query frequency
    last_check_time = None
    check_interval = timedelta(minutes=5)  # Adjust the interval as needed

    def process_request(self, request):
        """
        Synchronous method called before each request. It triggers the status check
        asynchronously, with a rate limit based on `check_interval` to reduce load.
        """
        if self.should_run_check():
            async_to_sync(self.check_and_update_relation_sets)()

    def should_run_check(self):
        """
        Determines whether the status check should be run based on the defined interval.
        """
        current_time = timezone.now()
        if not self.last_check_time or (current_time - self.last_check_time) > self.check_interval:
            self.last_check_time = current_time
            return True
        return False

    async def check_and_update_relation_sets(self):
        """
        This asynchronous function is responsible for checking and updating the 
        statuses of RelationSets in bulk. It uses the `update_status` method of 
        each RelationSet instance to evaluate and adjust their status based on 
        readiness conditions.
        """
        # Fetch RelationSets that need a status check asynchronously
        relation_sets = await sync_to_async(list)(
            RelationSet.objects.filter(status__in=['not_ready', 'ready_to_submit'])
        )

        # Update statuses for each RelationSet using the update_status method from Relationset model
        for relation_set in relation_sets:
            await sync_to_async(relation_set.update_status)()
