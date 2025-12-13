from django.conf import settings
from django.shortcuts import render, redirect

from selector.llm import OpenAIAdapter
from selector.models import AdminConfig, UserSession
from selector.services import Step1Service, Step2Service


def get_llm_adapter():
    return OpenAIAdapter(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL
    )


def _mark_session_completed(user_session, step):
    user_session.is_completed = True
    user_session.step_completed = step
    user_session.save()


def _get_pair_for_step(config, session_key):
    if config.current_step == 1:
        service = Step1Service(llm_adapter=get_llm_adapter())
    else:
        service = Step2Service()
    return service.get_current_pair(session_key=session_key)


def main_view(request):
    config = AdminConfig.objects.first()
    if not config or config.current_step == 0:
        return redirect('disabled')
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    user_session, _ = UserSession.objects.get_or_create(session_key=session_key)
    if user_session.is_completed and user_session.step_completed == config.current_step:
        return redirect('complete')
    pair = _get_pair_for_step(config, session_key)
    if not pair:
        _mark_session_completed(user_session, config.current_step)
        return redirect('complete')
    opt_a, opt_b = pair
    return render(request, 'selector/selection.html', {
        'option_a': opt_a,
        'option_b': opt_b,
        'step': config.current_step,
        'show_manual_input': config.current_step == 1
    })


def disabled_view(request):
    config = AdminConfig.objects.first()
    if config and config.current_step != 0:
        return redirect('main')
    return render(request, 'selector/disabled.html')


def complete_view(request):
    config = AdminConfig.objects.first()
    if not config or config.current_step == 0:
        return redirect('disabled')
    if not request.session.session_key:
        return redirect('main')
    session_key = request.session.session_key
    user_session = UserSession.objects.filter(session_key=session_key).first()
    if not user_session or not user_session.is_completed:
        return redirect('main')
    if user_session.step_completed != config.current_step:
        return redirect('main')
    return render(request, 'selector/complete.html')


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def _parse_selection_from_post(request):
    selected_id = int(request.POST.get('selected'))
    rejected_id = int(request.POST.get('rejected'))
    position = request.POST.get('position')
    selected_position = int(position) if position else None
    return selected_id, rejected_id, selected_position


def select_view(request):
    if request.method != 'POST':
        return redirect('main')
    config = AdminConfig.objects.first()
    if not config or config.current_step == 0:
        return redirect('disabled')
    session_key = request.session.session_key
    selected_id, rejected_id, selected_position = _parse_selection_from_post(request)
    ip_address = _get_client_ip(request)
    if config.current_step == 1:
        service = Step1Service(llm_adapter=get_llm_adapter())
        service.record_selection(session_key, selected_id, rejected_id, ip_address)
    else:
        service = Step2Service()
        service.record_selection(session_key, selected_id, rejected_id, ip_address, selected_position)
    return redirect('main')


def submit_manual_view(request):
    if request.method != 'POST':
        return redirect('main')
    config = AdminConfig.objects.first()
    if not config or config.current_step != 1:
        return redirect('main')
    session_key = request.session.session_key
    text = request.POST.get('text', '').strip()
    if text:
        service = Step1Service(llm_adapter=get_llm_adapter())
        service.submit_manual_option(session_key, text)
    return redirect('main')
