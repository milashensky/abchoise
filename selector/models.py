from django.db import models


class AdminConfig(models.Model):
    STEP_DISABLED = 0
    STEP_GENERATION = 1
    STEP_SELECTION = 2
    STEP_CHOICES = [
        (STEP_DISABLED, 'Disabled'),
        (STEP_GENERATION, 'Step 1 - Generation'),
        (STEP_SELECTION, 'Step 2 - Selection'),
    ]
    singleton_key = models.BooleanField(default=True, unique=True, editable=False)
    prompt = models.TextField()
    current_step = models.IntegerField(choices=STEP_CHOICES, default=STEP_DISABLED)
    rounds_count = models.IntegerField(default=5)


class Option(models.Model):
    SOURCE_CHOICES = [
        ('llm_generated', 'LLM Generated'),
        ('user_submitted', 'User Submitted'),
    ]
    text = models.CharField(max_length=255)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='llm_generated')
    created_at = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=64, blank=True, default='')

    def __str__(self):
        return f'[{self.id}]: {self.text}'


class Choice(models.Model):
    STEP_CHOICES = [
        (1, 'Step 1 - Generation'),
        (2, 'Step 2 - Selection'),
    ]
    POSITION_LEFT = 0
    POSITION_RIGHT = 1
    POSITION_CHOICES = [
        (POSITION_LEFT, 'Left'),
        (POSITION_RIGHT, 'Right'),
    ]
    selected = models.ForeignKey(Option, on_delete=models.CASCADE, related_name='selected_choices')
    rejected = models.ForeignKey(Option, on_delete=models.CASCADE, related_name='rejected_choices', null=True, blank=True)
    step = models.IntegerField(choices=STEP_CHOICES, default=1)
    selected_position = models.IntegerField(choices=POSITION_CHOICES, null=True, blank=True)
    session_id = models.CharField(max_length=64, blank=True, default='')
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserSession(models.Model):
    session_key = models.CharField(max_length=64, unique=True)
    current_round = models.IntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    step_completed = models.IntegerField(default=0)
