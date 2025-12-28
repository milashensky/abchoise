from selector.models import AdminConfig, Option, Choice, UserSession
from selector.llm import LLMAdapter


class Step1Service:
    def __init__(self, llm_adapter: LLMAdapter):
        self.llm_adapter = llm_adapter

    def _get_or_create_option(self, text: str, source: str = 'llm_generated', session_id: str = '') -> Option:
        normalized = text.strip().upper()
        option, _ = Option.objects.get_or_create(
            text=normalized,
            defaults={'source': source, 'session_id': session_id}
        )
        return option

    def get_current_pair(self, session_key: str) -> tuple[Option, Option] | None:
        config = AdminConfig.objects.first()
        session, _ = UserSession.objects.get_or_create(session_key=session_key)
        if session.current_round >= config.rounds_count:
            return None
        history = list(
            Choice.objects.filter(session_id=session_key, step=1, selected__isnull=False)
            .values_list('selected__text', flat=True)
        )
        rejected = list(
            Choice.objects.filter(session_id=session_key, step=1, selected__isnull=True)
            .values_list('rejected__text', flat=True)
        )
        opt_a_text, opt_b_text = self.llm_adapter.generate_options(
            prompt=config.prompt,
            history=history,
            rejected=rejected
        )
        opt_a = self._get_or_create_option(opt_a_text, session_id=session_key)
        opt_b = self._get_or_create_option(opt_b_text, session_id=session_key)
        return opt_a, opt_b

    def record_selection(self, session_key: str, selected_id: int, rejected_id: int, ip_address: str):
        config = AdminConfig.objects.first()
        session, _ = UserSession.objects.get_or_create(session_key=session_key)
        Choice.objects.create(
            selected_id=selected_id,
            rejected_id=rejected_id,
            step=1,
            session_id=session_key,
            ip_address=ip_address
        )
        session.current_round += 1
        if session.current_round >= config.rounds_count:
            session.is_completed = True
            session.step_completed = 1
        session.save()

    def submit_manual_option(self, session_key: str, text: str) -> Option:
        option = self._get_or_create_option(text, source='user_submitted', session_id=session_key)
        Choice.objects.create(
            selected=option,
            rejected=None,
            step=1,
            session_id=session_key
        )
        return option

    def record_neither(self, session_key: str, option_a_id: int, option_b_id: int, ip_address: str):
        config = AdminConfig.objects.first()
        session, _ = UserSession.objects.get_or_create(session_key=session_key)
        Choice.objects.create(
            selected=None,
            rejected_id=option_a_id,
            step=1,
            session_id=session_key,
            ip_address=ip_address
        )
        Choice.objects.create(
            selected=None,
            rejected_id=option_b_id,
            step=1,
            session_id=session_key,
            ip_address=ip_address
        )
        session.current_round += 1
        if session.current_round >= config.rounds_count:
            session.is_completed = True
            session.step_completed = 1
        session.save()


class Step2Service:
    def get_eligible_options(self) -> list[Option]:
        selected_ids = Choice.objects.filter(step=1).values_list('selected_id', flat=True).distinct()
        return list(Option.objects.filter(id__in=selected_ids).order_by('id'))

    def get_total_rounds(self) -> int:
        options = self.get_eligible_options()
        return max(0, len(options) - 1)

    def _get_initial_pair(self, options: list[Option]) -> tuple[Option, Option]:
        return options[0], options[1]

    def _get_last_step2_choice(self, session_key: str) -> Choice | None:
        return Choice.objects.filter(
            session_id=session_key, step=2
        ).order_by('-created_at').first()

    def _get_next_challenger(self, options: list[Option], round_number: int) -> Option | None:
        challenger_index = round_number + 1
        if challenger_index >= len(options):
            return None
        return options[challenger_index]

    def _order_pair_by_winner_position(self, winner: Option, challenger: Option, last_choice: Choice) -> tuple[Option, Option]:
        if last_choice.selected_position == Choice.POSITION_RIGHT:
            return challenger, winner
        return winner, challenger

    def get_current_pair(self, session_key: str) -> tuple[Option, Option] | None:
        session, _ = UserSession.objects.get_or_create(session_key=session_key)
        options = self.get_eligible_options()
        if len(options) < 2:
            return None
        if session.current_round >= len(options) - 1:
            return None
        if session.current_round == 0:
            return self._get_initial_pair(options)
        last_choice = self._get_last_step2_choice(session_key)
        if not last_choice:
            return self._get_initial_pair(options)
        challenger = self._get_next_challenger(options, session.current_round)
        if not challenger:
            return None
        return self._order_pair_by_winner_position(last_choice.selected, challenger, last_choice)

    def record_selection(self, session_key: str, selected_id: int, rejected_id: int, ip_address: str, selected_position: int = None):
        session, _ = UserSession.objects.get_or_create(session_key=session_key)
        Choice.objects.create(
            selected_id=selected_id,
            rejected_id=rejected_id,
            step=2,
            selected_position=selected_position,
            session_id=session_key,
            ip_address=ip_address
        )
        session.current_round += 1
        total_rounds = self.get_total_rounds()
        if session.current_round >= total_rounds:
            session.is_completed = True
            session.step_completed = 2
        session.save()

    def _calculate_streak(self, choices) -> tuple[Option | None, int]:
        current_streak = 0
        current_option = None
        longest_streak = 0
        longest_streak_option = None
        for choice in choices:
            if choice.selected == current_option:
                current_streak += 1
            else:
                current_option = choice.selected
                current_streak = 1
            if current_streak > longest_streak:
                longest_streak = current_streak
                longest_streak_option = current_option
        return longest_streak_option, longest_streak

    def get_streak_stats(self, session_key: str) -> dict:
        choices = Choice.objects.filter(session_id=session_key, step=2).order_by('created_at')
        longest_streak_option, longest_streak = self._calculate_streak(choices)
        return {
            'longest_streak_option': longest_streak_option,
            'longest_streak_count': longest_streak
        }

    def get_final_winner(self, session_key: str) -> Option | None:
        last_choice = self._get_last_step2_choice(session_key)
        return last_choice.selected if last_choice else None
