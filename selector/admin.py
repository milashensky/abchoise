from django.contrib import admin
from django.db import models
from django.db.models import Count
from django.shortcuts import render
from django.urls import path

from selector.models import AdminConfig, Choice, Option, UserSession


def _calculate_session_streak(choices):
    current_streak = 0
    current_option = None
    longest_streak = 0
    longest_option = None
    for choice in choices:
        if choice.selected == current_option:
            current_streak += 1
        else:
            current_option = choice.selected
            current_streak = 1
        if current_streak > longest_streak:
            longest_streak = current_streak
            longest_option = current_option
    return longest_option, longest_streak


def _get_distinct_ips(step):
    return Choice.objects.filter(step=step).values_list('ip_address', flat=True).distinct()


@admin.register(AdminConfig)
class AdminConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_current_step_display', 'rounds_count']
    fields = ['prompt', 'current_step', 'rounds_count']

    def has_add_permission(self, request):
        return not AdminConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'text', 'source', 'session_id', 'created_at', 'selection_count']
    list_filter = ['source', 'created_at']
    search_fields = ['text', 'session_id']
    change_list_template = 'admin/selector/option/change_list.html'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(sel_count=Count('selected_choices'))

    def selection_count(self, obj):
        return obj.sel_count

    selection_count.admin_order_field = 'sel_count'
    selection_count.short_description = 'Times Selected'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('results/step1/', self.admin_site.admin_view(self.step1_popularity_view), name='results_step1'),
            path('results/step2-streak/', self.admin_site.admin_view(self.step2_streak_view), name='results_step2_streak'),
            path('results/step2-final/', self.admin_site.admin_view(self.step2_final_view), name='results_step2_final'),
        ]
        return custom_urls + urls

    def step1_popularity_view(self, request):
        ip_filter = request.GET.get('ip')
        choices_qs = Choice.objects.filter(step=1)
        if ip_filter:
            choices_qs = choices_qs.filter(ip_address=ip_filter)
        selected_ids = choices_qs.values_list('selected_id', flat=True)
        options = (
            Option.objects.filter(id__in=selected_ids)
            .annotate(count=Count('selected_choices', filter=models.Q(selected_choices__step=1)))
            .order_by('-count')
        )
        context = {
            **self.admin_site.each_context(request),
            'title': 'Step 1 - Popularity',
            'options': options,
            'ips': _get_distinct_ips(1),
            'selected_ip': ip_filter,
        }
        return render(request, 'admin/selector/step1_popularity.html', context)

    def step2_streak_view(self, request):
        ip_filter = request.GET.get('ip')
        choices_qs = Choice.objects.filter(step=2).order_by('session_id', 'created_at')
        if ip_filter:
            choices_qs = choices_qs.filter(ip_address=ip_filter)
        streak_data = {}
        for session_id in choices_qs.values_list('session_id', flat=True).distinct():
            session_choices = choices_qs.filter(session_id=session_id).order_by('created_at')
            longest_option, longest_streak = _calculate_session_streak(session_choices)
            if longest_option:
                key = longest_option.id
                if key not in streak_data:
                    streak_data[key] = {'option': longest_option, 'max_streak': 0, 'sessions': 0}
                if longest_streak > streak_data[key]['max_streak']:
                    streak_data[key]['max_streak'] = longest_streak
                streak_data[key]['sessions'] += 1
        results = sorted(streak_data.values(), key=lambda x: -x['max_streak'])
        context = {
            **self.admin_site.each_context(request),
            'title': 'Step 2 - Longest Streak',
            'results': results,
            'ips': _get_distinct_ips(2),
            'selected_ip': ip_filter,
        }
        return render(request, 'admin/selector/step2_streak.html', context)

    def step2_final_view(self, request):
        ip_filter = request.GET.get('ip')
        choices_qs = Choice.objects.filter(step=2)
        if ip_filter:
            choices_qs = choices_qs.filter(ip_address=ip_filter)
        final_counts = {}
        for session_id in choices_qs.values_list('session_id', flat=True).distinct():
            last_choice = choices_qs.filter(session_id=session_id).order_by('-created_at').first()
            if last_choice:
                opt = last_choice.selected
                if opt.id not in final_counts:
                    final_counts[opt.id] = {'option': opt, 'count': 0}
                final_counts[opt.id]['count'] += 1
        results = sorted(final_counts.values(), key=lambda x: -x['count'])
        context = {
            **self.admin_site.each_context(request),
            'title': 'Step 2 - Final Winners',
            'results': results,
            'ips': _get_distinct_ips(2),
            'selected_ip': ip_filter,
        }
        return render(request, 'admin/selector/step2_final.html', context)


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'selected', 'rejected', 'step', 'session_id', 'ip_address', 'created_at']
    list_filter = ['step', 'ip_address', 'created_at']
    search_fields = ['session_id', 'ip_address']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['session_key', 'current_round', 'is_completed', 'step_completed']
    list_filter = ['is_completed', 'step_completed']
    search_fields = ['session_key']
