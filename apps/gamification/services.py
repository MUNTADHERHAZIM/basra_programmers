from .models import Badge, TraineeBadge, ActivityPointsLog
from apps.users.models import TraineeProfile
from django.db import transaction

def award_points(trainee, points, reason):
    """
    Awards points to a trainee user, updates their profile total points,
    logs the activity, and checks for newly unlocked badges.
    """
    with transaction.atomic():
        # Log points activity
        ActivityPointsLog.objects.create(
            trainee=trainee,
            points=points,
            reason=reason
        )
        
        # Update total profile points
        profile = trainee.trainee_profile
        profile.points += points
        profile.save()
        
        # Check if badges can be unlocked
        unlocked = check_and_unlock_badges(trainee, profile.points)
        return unlocked

def check_and_unlock_badges(trainee, current_points=None):
    """
    Checks if a trainee qualifies for any automated badges they haven't earned yet.
    """
    if current_points is None:
        try:
            current_points = trainee.trainee_profile.points
        except Exception:
            return []
        
    earned_badge_ids = TraineeBadge.objects.filter(trainee=trainee).values_list('badge_id', flat=True)
    # Only automatically unlock attendance or points milestone badges if threshold reached
    unearned_badges = Badge.objects.exclude(id__in=earned_badge_ids).filter(name__icontains="حضور")
    
    unlocked_badges = []
    for badge in unearned_badges:
        if current_points >= badge.points_required:
            TraineeBadge.objects.create(trainee=trainee, badge=badge)
            unlocked_badges.append(badge)
            
    return unlocked_badges
