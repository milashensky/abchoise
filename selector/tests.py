from abc import ABC
import inspect
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from selector.models import AdminConfig, Option, Choice, UserSession
from selector.services import Step1Service, Step2Service
from selector.llm import LLMAdapter, OpenAIAdapter, LLMError


class AdminConfigModelTest(TestCase):
    def test_stores_prompt_text(self):
        config = AdminConfig.objects.create(prompt="Generate mascot names")
        self.assertEqual(config.prompt, "Generate mascot names")

    def test_stores_current_step(self):
        config = AdminConfig.objects.create(prompt="test", current_step=1)
        steps = [(1, 1), (2, 2), (0, 0)]
        for step_value, expected in steps:
            with self.subTest(step=step_value):
                config.current_step = step_value
                config.save()
                config.refresh_from_db()
                self.assertEqual(config.current_step, expected)

    def test_stores_rounds_count(self):
        config = AdminConfig.objects.create(prompt="test", rounds_count=5)
        self.assertEqual(config.rounds_count, 5)

    def test_singleton_constraint(self):
        AdminConfig.objects.create(prompt="first")
        with self.assertRaises(Exception):
            AdminConfig.objects.create(prompt="second")


class OptionModelTest(TestCase):
    def test_stores_text_value(self):
        option = Option.objects.create(text="Alex")
        self.assertEqual(option.text, "Alex")

    def test_stores_source(self):
        sources = [
            ("llm_generated", "llm_generated"),
            ("user_submitted", "user_submitted"),
        ]
        for source, expected in sources:
            with self.subTest(source=source):
                option = Option.objects.create(text="Test", source=source)
                self.assertEqual(option.source, expected)

    def test_stores_created_at(self):
        before = timezone.now()
        option = Option.objects.create(text="Alex")
        after = timezone.now()
        with self.subTest(check="lower_bound"):
            self.assertGreaterEqual(option.created_at, before)
        with self.subTest(check="upper_bound"):
            self.assertLessEqual(option.created_at, after)

    def test_stores_session_id(self):
        option = Option.objects.create(text="Alex", session_id="abc123")
        self.assertEqual(option.session_id, "abc123")


class ChoiceModelTest(TestCase):
    def test_stores_selected_and_rejected_options(self):
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        choice = Choice.objects.create(selected=opt_a, rejected=opt_b)
        with self.subTest(field="selected"):
            self.assertEqual(choice.selected, opt_a)
        with self.subTest(field="rejected"):
            self.assertEqual(choice.rejected, opt_b)

    def test_stores_step(self):
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        steps = [(1, 1), (2, 2)]
        for step, expected in steps:
            with self.subTest(step=step):
                choice = Choice.objects.create(selected=opt_a, rejected=opt_b, step=step)
                self.assertEqual(choice.step, expected)

    def test_stores_session_id_and_ip(self):
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        choice = Choice.objects.create(
            selected=opt_a, rejected=opt_b,
            session_id="abc123", ip_address="192.168.1.1"
        )
        with self.subTest(field="session_id"):
            self.assertEqual(choice.session_id, "abc123")
        with self.subTest(field="ip_address"):
            self.assertEqual(choice.ip_address, "192.168.1.1")

    def test_stores_created_at(self):
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        before = timezone.now()
        choice = Choice.objects.create(selected=opt_a, rejected=opt_b)
        after = timezone.now()
        with self.subTest(check="lower_bound"):
            self.assertGreaterEqual(choice.created_at, before)
        with self.subTest(check="upper_bound"):
            self.assertLessEqual(choice.created_at, after)


class UserSessionModelTest(TestCase):
    def test_stores_session_key(self):
        session = UserSession.objects.create(session_key="abc123")
        self.assertEqual(session.session_key, "abc123")

    def test_stores_current_round(self):
        session = UserSession.objects.create(session_key="abc", current_round=3)
        self.assertEqual(session.current_round, 3)

    def test_stores_is_completed(self):
        session = UserSession.objects.create(session_key="abc", is_completed=True)
        self.assertTrue(session.is_completed)

    def test_stores_step_completed(self):
        session = UserSession.objects.create(session_key="abc", step_completed=1)
        self.assertEqual(session.step_completed, 1)


class LLMAdapterInterfaceTest(TestCase):
    def test_base_class_defines_generate_options_method(self):
        with self.subTest(check="is_abc"):
            self.assertTrue(issubclass(LLMAdapter, ABC))
        with self.subTest(check="has_method"):
            self.assertTrue(hasattr(LLMAdapter, 'generate_options'))

    def test_generate_options_signature(self):
        sig = inspect.signature(LLMAdapter.generate_options)
        params = list(sig.parameters.keys())
        required_params = ['self', 'prompt', 'history']
        for param in required_params:
            with self.subTest(param=param):
                self.assertIn(param, params)


class OpenAIAdapterTest(TestCase):
    def test_implements_interface(self):
        self.assertTrue(issubclass(OpenAIAdapter, LLMAdapter))

    def test_constructs_prompt_with_domain_and_criteria(self):
        adapter = OpenAIAdapter(api_key="test-key")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Option1\nOption2"))]
        with patch.object(adapter, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            adapter.generate_options(
                prompt="Domain: mascot names. Criteria: playful, memorable",
                history=[]
            )
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs['messages']
            user_message = next(m for m in messages if m['role'] == 'user')
            with self.subTest(check="domain"):
                self.assertIn('mascot names', user_message['content'])
            with self.subTest(check="criteria"):
                self.assertIn('playful', user_message['content'])

    def test_includes_history_in_prompt(self):
        adapter = OpenAIAdapter(api_key="test-key")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Option1\nOption2"))]
        with patch.object(adapter, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            adapter.generate_options(
                prompt="Generate names",
                history=["Alex", "Pablo"]
            )
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs['messages']
            user_message = next(m for m in messages if m['role'] == 'user')
            history_items = ["Alex", "Pablo"]
            for item in history_items:
                with self.subTest(history_item=item):
                    self.assertIn(item, user_message['content'])

    def test_parses_response_into_two_options(self):
        adapter = OpenAIAdapter(api_key="test-key")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Alex\nPablo"))]
        with patch.object(adapter, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            opt_a, opt_b = adapter.generate_options(prompt="test", history=[])
            with self.subTest(option="a"):
                self.assertEqual(opt_a, "Alex")
            with self.subTest(option="b"):
                self.assertEqual(opt_b, "Pablo")

    def test_handles_api_error(self):
        adapter = OpenAIAdapter(api_key="test-key")
        with patch.object(adapter, 'client') as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("API Error")
            with self.assertRaises(LLMError):
                adapter.generate_options(prompt="test", history=[])


class PromptConstructionTest(TestCase):
    def test_includes_rejected_options_with_deprioritize_instruction(self):
        adapter = OpenAIAdapter(api_key="test-key")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Opt1\nOpt2"))]
        with patch.object(adapter, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            adapter.generate_options(
                prompt="Generate names",
                history=["Alex"],
                rejected=["BadOption1", "BadOption2"]
            )
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs['messages']
            user_message = next(m for m in messages if m['role'] == 'user')
            with self.subTest(check="deprioritize_keyword"):
                self.assertIn("deprioritize", user_message['content'].lower())
            with self.subTest(check="rejected_option_1"):
                self.assertIn("BadOption1", user_message['content'])
            with self.subTest(check="rejected_option_2"):
                self.assertIn("BadOption2", user_message['content'])

    def test_system_prompt_instructs_exploitation_exploration(self):
        adapter = OpenAIAdapter(api_key="test-key")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Opt1\nOpt2"))]
        with patch.object(adapter, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            adapter.generate_options(prompt="test", history=["Alex"])
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs['messages']
            system_msg = next(m for m in messages if m['role'] == 'system')
            keywords = ['exploit', 'explor']
            for keyword in keywords:
                with self.subTest(keyword=keyword):
                    self.assertIn(keyword, system_msg['content'].lower())


class Step1ServiceTest(TestCase):
    def setUp(self):
        AdminConfig.objects.create(
            prompt="Domain: mascot names. Criteria: playful, memorable",
            current_step=1,
            rounds_count=5
        )

    def test_llm_generated_option_normalizes_text(self):
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ('  alex  ', '  pablo  ')
        service = Step1Service(llm_adapter=mock_adapter)
        opt_a, opt_b = service.get_current_pair(session_key='sess1')
        with self.subTest('should normalize option a'):
            self.assertEqual(opt_a.text, 'ALEX')
        with self.subTest('should normalize option b'):
            self.assertEqual(opt_b.text, 'PABLO')

    def test_llm_generated_option_reuses_existing_option(self):
        existing = Option.objects.create(text='ALEX')
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ('  alex  ', 'Pablo')
        service = Step1Service(llm_adapter=mock_adapter)
        opt_a, opt_b = service.get_current_pair(session_key='sess1')
        with self.subTest('should reuse existing option'):
            self.assertEqual(opt_a.id, existing.id)
        with self.subTest('should not create duplicate'):
            self.assertEqual(Option.objects.filter(text='ALEX').count(), 1)

    def test_manual_option_normalizes_input(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        option = service.submit_manual_option(session_key='sess1', text='  my option  ')
        self.assertEqual(option.text, 'MY OPTION')

    def test_manual_option_reuses_existing_option(self):
        existing = Option.objects.create(text='MY OPTION')
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        option = service.submit_manual_option(session_key='sess1', text='  my option  ')
        with self.subTest('should reuse existing option'):
            self.assertEqual(option.id, existing.id)
        with self.subTest('should not create duplicate'):
            self.assertEqual(Option.objects.filter(text='MY OPTION').count(), 1)

    def test_get_pair_for_new_session(self):
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ("Alex", "Pablo")
        service = Step1Service(llm_adapter=mock_adapter)
        opt_a, opt_b = service.get_current_pair(session_key="new-session")
        with self.subTest(option="a"):
            self.assertEqual(opt_a.text, "ALEX")
        with self.subTest(option="b"):
            self.assertEqual(opt_b.text, "PABLO")

    def test_get_pair_uses_history_after_selection(self):
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ("Maria", "Hope")
        service = Step1Service(llm_adapter=mock_adapter)
        opt_alex = Option.objects.create(text="Alex", session_id="sess1")
        opt_pablo = Option.objects.create(text="Pablo", session_id="sess1")
        Choice.objects.create(selected=opt_alex, rejected=opt_pablo, session_id="sess1", step=1)
        service.get_current_pair(session_key="sess1")
        call_args = mock_adapter.generate_options.call_args
        history = call_args.kwargs.get('history') or call_args.args[1]
        self.assertIn("Alex", history)

    def test_respects_rounds_count_limit(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        UserSession.objects.create(session_key="sess1", current_round=5)
        result = service.get_current_pair(session_key="sess1")
        self.assertIsNone(result)

    def test_record_selection_creates_choice(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        opt_a = Option.objects.create(text="Alex", session_id="sess1")
        opt_b = Option.objects.create(text="Pablo", session_id="sess1")
        service.record_selection(
            session_key="sess1",
            selected_id=opt_a.id,
            rejected_id=opt_b.id,
            ip_address="192.168.1.1"
        )
        choice = Choice.objects.get(session_id="sess1")
        assertions = [
            ("selected", choice.selected, opt_a),
            ("rejected", choice.rejected, opt_b),
            ("step", choice.step, 1),
            ("ip_address", choice.ip_address, "192.168.1.1"),
        ]
        for field, actual, expected in assertions:
            with self.subTest(field=field):
                self.assertEqual(actual, expected)

    def test_record_selection_increments_round(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        opt_a = Option.objects.create(text="Alex", session_id="sess1")
        opt_b = Option.objects.create(text="Pablo", session_id="sess1")
        service.record_selection(
            session_key="sess1",
            selected_id=opt_a.id,
            rejected_id=opt_b.id,
            ip_address="192.168.1.1"
        )
        session = UserSession.objects.get(session_key="sess1")
        self.assertEqual(session.current_round, 1)

    def test_record_selection_marks_complete_after_all_rounds(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        UserSession.objects.create(session_key="sess1", current_round=4)
        opt_a = Option.objects.create(text="Alex", session_id="sess1")
        opt_b = Option.objects.create(text="Pablo", session_id="sess1")
        service.record_selection(
            session_key="sess1",
            selected_id=opt_a.id,
            rejected_id=opt_b.id,
            ip_address="192.168.1.1"
        )
        session = UserSession.objects.get(session_key="sess1")
        with self.subTest(field="is_completed"):
            self.assertTrue(session.is_completed)
        with self.subTest(field="step_completed"):
            self.assertEqual(session.step_completed, 1)

    def test_submit_manual_option_creates_user_submitted_option(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        option = service.submit_manual_option(session_key="sess1", text="MyCustomName")
        assertions = [
            ("text", option.text, "MYCUSTOMNAME"),
            ("source", option.source, "user_submitted"),
            ("session_id", option.session_id, "sess1"),
        ]
        for field, actual, expected in assertions:
            with self.subTest(field=field):
                self.assertEqual(actual, expected)

    def test_submit_manual_option_creates_vote(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        option = service.submit_manual_option(session_key="sess1", text="MyCustomName")
        choice = Choice.objects.get(session_id="sess1", step=1)
        self.assertEqual(choice.selected, option)

    def test_submit_manual_option_included_in_llm_history(self):
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ("NewOpt1", "NewOpt2")
        service = Step1Service(llm_adapter=mock_adapter)
        service.submit_manual_option(session_key="sess1", text="MyCustomName")
        service.get_current_pair(session_key="sess1")
        call_args = mock_adapter.generate_options.call_args
        history = call_args.kwargs.get('history') or call_args.args[1]
        self.assertIn("MYCUSTOMNAME", history)

    def test_submit_manual_option_eligible_for_step2(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        option = service.submit_manual_option(session_key="sess1", text="MyCustomName")
        step2_service = Step2Service()
        eligible = step2_service.get_eligible_options()
        self.assertIn(option, eligible)

    def test_record_neither_creates_two_choices_with_null_selected(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        opt_a = Option.objects.create(text="Alex", session_id="sess1")
        opt_b = Option.objects.create(text="Pablo", session_id="sess1")
        service.record_neither(
            session_key="sess1",
            option_a_id=opt_a.id,
            option_b_id=opt_b.id,
            ip_address="192.168.1.1"
        )
        choices = Choice.objects.filter(session_id="sess1", selected__isnull=True)
        with self.subTest(check="count"):
            self.assertEqual(choices.count(), 2)
        rejected_ids = set(choices.values_list('rejected_id', flat=True))
        with self.subTest(check="rejected_ids"):
            self.assertEqual(rejected_ids, {opt_a.id, opt_b.id})

    def test_record_neither_increments_round_counter(self):
        mock_adapter = MagicMock()
        service = Step1Service(llm_adapter=mock_adapter)
        opt_a = Option.objects.create(text="Alex", session_id="sess1")
        opt_b = Option.objects.create(text="Pablo", session_id="sess1")
        service.record_neither(
            session_key="sess1",
            option_a_id=opt_a.id,
            option_b_id=opt_b.id,
            ip_address="192.168.1.1"
        )
        session = UserSession.objects.get(session_key="sess1")
        self.assertEqual(session.current_round, 1)

    def test_get_pair_passes_rejected_history_to_llm(self):
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ("NewOpt1", "NewOpt2")
        service = Step1Service(llm_adapter=mock_adapter)
        opt_bad1 = Option.objects.create(text="BadOption1", session_id="sess1")
        opt_bad2 = Option.objects.create(text="BadOption2", session_id="sess1")
        Choice.objects.create(selected=None, rejected=opt_bad1, step=1, session_id="sess1")
        Choice.objects.create(selected=None, rejected=opt_bad2, step=1, session_id="sess1")
        service.get_current_pair(session_key="sess1")
        call_args = mock_adapter.generate_options.call_args
        rejected = call_args.kwargs.get('rejected') or call_args.args[2]
        with self.subTest(check="bad1"):
            self.assertIn("BadOption1", rejected)
        with self.subTest(check="bad2"):
            self.assertIn("BadOption2", rejected)

    def test_rejected_options_accumulate_across_multiple_neither_clicks(self):
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ("NewOpt", "NewOpt2")
        service = Step1Service(llm_adapter=mock_adapter)
        opt_a = Option.objects.create(text="Rejected1", session_id="sess1")
        opt_b = Option.objects.create(text="Rejected2", session_id="sess1")
        service.record_neither("sess1", opt_a.id, opt_b.id, "127.0.0.1")
        opt_c = Option.objects.create(text="Rejected3", session_id="sess1")
        opt_d = Option.objects.create(text="Rejected4", session_id="sess1")
        service.record_neither("sess1", opt_c.id, opt_d.id, "127.0.0.1")
        service.get_current_pair(session_key="sess1")
        call_args = mock_adapter.generate_options.call_args
        rejected = call_args.kwargs.get('rejected') or call_args.args[2]
        expected = ["Rejected1", "Rejected2", "Rejected3", "Rejected4"]
        for item in expected:
            with self.subTest(rejected_item=item):
                self.assertIn(item, rejected)


class Step2ServiceTest(TestCase):
    def _create_eligible_options(self, count):
        options = [Option.objects.create(text=f"Opt{i}") for i in range(count)]
        for opt in options:
            other = options[0] if opt != options[0] else options[1]
            Choice.objects.create(selected=opt, rejected=other, step=1)
        return options

    def _select_option(self, service, session_key, pair, position):
        opt_left, opt_right = pair
        if position == 'left':
            selected, rejected = opt_left, opt_right
            pos_value = Choice.POSITION_LEFT
        else:
            selected, rejected = opt_right, opt_left
            pos_value = Choice.POSITION_RIGHT
        service.record_selection(
            session_key=session_key,
            selected_id=selected.id,
            rejected_id=rejected.id,
            ip_address="127.0.0.1",
            selected_position=pos_value
        )
        return selected, rejected

    def test_get_eligible_options_returns_only_selected(self):
        opt_selected = Option.objects.create(text="Alex")
        opt_rejected = Option.objects.create(text="Pablo")
        opt_never_shown = Option.objects.create(text="Maria")
        Choice.objects.create(selected=opt_selected, rejected=opt_rejected, step=1)
        service = Step2Service()
        eligible = service.get_eligible_options()
        cases = [
            ("selected_in", opt_selected, True),
            ("rejected_not_in", opt_rejected, False),
            ("never_shown_not_in", opt_never_shown, False),
        ]
        for name, opt, should_be_in in cases:
            with self.subTest(case=name):
                if should_be_in:
                    self.assertIn(opt, eligible)
                else:
                    self.assertNotIn(opt, eligible)

    def test_total_rounds_returns_n_minus_1(self):
        self._create_eligible_options(4)
        service = Step2Service()
        total_rounds = service.get_total_rounds()
        self.assertEqual(total_rounds, 3)

    def test_first_pair_is_first_two_options(self):
        self._create_eligible_options(4)
        UserSession.objects.create(session_key="sess1", current_round=0)
        service = Step2Service()
        pair = service.get_current_pair(session_key="sess1")
        eligible = service.get_eligible_options()
        with self.subTest(position="left"):
            self.assertEqual(pair[0], eligible[0])
        with self.subTest(position="right"):
            self.assertEqual(pair[1], eligible[1])

    def test_winner_faces_next_challenger(self):
        self._create_eligible_options(4)
        UserSession.objects.create(session_key="sess1", current_round=1)
        service = Step2Service()
        eligible = service.get_eligible_options()
        Choice.objects.create(
            selected=eligible[1], rejected=eligible[0], step=2, session_id="sess1"
        )
        pair = service.get_current_pair(session_key="sess1")
        with self.subTest(position="winner"):
            self.assertEqual(pair[0], eligible[1])
        with self.subTest(position="challenger"):
            self.assertEqual(pair[1], eligible[2])

    def test_get_current_pair_returns_pair_for_round(self):
        self._create_eligible_options(3)
        UserSession.objects.create(session_key="sess1", current_round=0)
        service = Step2Service()
        pair = service.get_current_pair(session_key="sess1")
        with self.subTest(check="not_none"):
            self.assertIsNotNone(pair)
        with self.subTest(check="length"):
            self.assertEqual(len(pair), 2)

    def test_record_selection_creates_step2_choice(self):
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        service = Step2Service()
        service.record_selection(
            session_key="sess1",
            selected_id=opt_a.id,
            rejected_id=opt_b.id,
            ip_address="192.168.1.1"
        )
        choice = Choice.objects.get(session_id="sess1", step=2)
        with self.subTest(field="selected"):
            self.assertEqual(choice.selected, opt_a)
        with self.subTest(field="rejected"):
            self.assertEqual(choice.rejected, opt_b)

    def test_get_streak_stats_for_session(self):
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        opt_c = Option.objects.create(text="Maria")
        Choice.objects.create(selected=opt_a, rejected=opt_b, step=2, session_id="sess1")
        Choice.objects.create(selected=opt_a, rejected=opt_c, step=2, session_id="sess1")
        Choice.objects.create(selected=opt_a, rejected=opt_b, step=2, session_id="sess1")
        service = Step2Service()
        stats = service.get_streak_stats(session_key="sess1")
        with self.subTest(field="option"):
            self.assertEqual(stats['longest_streak_option'], opt_a)
        with self.subTest(field="count"):
            self.assertEqual(stats['longest_streak_count'], 3)

    def test_get_final_winner(self):
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        Choice.objects.create(selected=opt_a, rejected=opt_b, step=2, session_id="sess1")
        Choice.objects.create(selected=opt_b, rejected=opt_a, step=2, session_id="sess1")
        service = Step2Service()
        final = service.get_final_winner(session_key="sess1")
        self.assertEqual(final, opt_b)

    def test_selected_option_continues_to_next_round(self):
        self._create_eligible_options(3)
        service = Step2Service()
        variants = ['left', 'right']
        for position in variants:
            with self.subTest(select=position):
                Choice.objects.filter(step=2).delete()
                UserSession.objects.all().delete()
                session_key = f"sess_{position}"
                pair1 = service.get_current_pair(session_key=session_key)
                self.assertIsNotNone(pair1)
                selected, rejected = self._select_option(service, session_key, pair1, position)
                pair2 = service.get_current_pair(session_key=session_key)
                self.assertIsNotNone(pair2, "Should have more pairs")
                next_left, next_right = pair2
                self.assertIn(selected, [next_left, next_right])
                self.assertNotIn(rejected, [next_left, next_right])

    def test_winner_preserves_position(self):
        self._create_eligible_options(3)
        service = Step2Service()
        variants = [
            {'position': 'left', 'expected_index': 0},
            {'position': 'right', 'expected_index': 1},
        ]
        for variant in variants:
            with self.subTest(select=variant['position']):
                Choice.objects.filter(step=2).delete()
                UserSession.objects.all().delete()
                session_key = f"sess_{variant['position']}"
                pair1 = service.get_current_pair(session_key=session_key)
                selected, _ = self._select_option(service, session_key, pair1, variant['position'])
                pair2 = service.get_current_pair(session_key=session_key)
                self.assertEqual(pair2[variant['expected_index']], selected)


class MainViewTest(TestCase):
    def setUp(self):
        AdminConfig.objects.create(
            prompt="Domain: mascot names",
            current_step=1,
            rounds_count=5
        )

    def test_redirects_to_disabled_when_step_0(self):
        config = AdminConfig.objects.first()
        config.current_step = 0
        config.save()
        response = self.client.get('/')
        self.assertRedirects(response, '/disabled/')

    def test_shows_step1_interface_when_step_1(self):
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ("Alex", "Pablo")
        with patch('selector.views.get_llm_adapter', return_value=mock_adapter):
            response = self.client.get('/')
            with self.subTest(check="status"):
                self.assertEqual(response.status_code, 200)
            with self.subTest(check="template"):
                self.assertTemplateUsed(response, 'selector/selection.html')

    def test_shows_step2_interface_when_step_2(self):
        config = AdminConfig.objects.first()
        config.current_step = 2
        config.save()
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        Choice.objects.create(selected=opt_a, rejected=opt_b, step=1)
        Choice.objects.create(selected=opt_b, rejected=opt_a, step=1)
        response = self.client.get('/')
        with self.subTest(check="status"):
            self.assertEqual(response.status_code, 200)
        with self.subTest(check="template"):
            self.assertTemplateUsed(response, 'selector/selection.html')

    def test_shows_completion_when_user_done(self):
        session = self.client.session
        session.save()
        UserSession.objects.create(
            session_key=session.session_key,
            is_completed=True,
            step_completed=1
        )
        response = self.client.get('/')
        self.assertRedirects(response, '/complete/')


class DisabledViewRedirectTest(TestCase):
    def test_redirects_to_main_when_step_enabled(self):
        AdminConfig.objects.create(prompt="test", current_step=1, rounds_count=5)
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ("A", "B")
        with patch('selector.views.get_llm_adapter', return_value=mock_adapter):
            response = self.client.get('/disabled/')
            self.assertRedirects(response, '/')

    def test_stays_on_disabled_when_step_0(self):
        AdminConfig.objects.create(prompt="test", current_step=0)
        response = self.client.get('/disabled/')
        self.assertEqual(response.status_code, 200)


class NeitherViewTest(TestCase):
    def setUp(self):
        AdminConfig.objects.create(prompt="test", current_step=1, rounds_count=5)

    def test_neither_view_records_rejection_and_redirects(self):
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        response = self.client.post('/neither/', {
            'option_a': opt_a.id,
            'option_b': opt_b.id
        })
        with self.subTest(check="redirect"):
            self.assertRedirects(response, '/')
        choices = Choice.objects.filter(selected__isnull=True)
        with self.subTest(check="choices_created"):
            self.assertEqual(choices.count(), 2)

    def test_neither_button_shown_in_step1(self):
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ("Alex", "Pablo")
        with patch('selector.views.get_llm_adapter', return_value=mock_adapter):
            response = self.client.get('/')
            self.assertContains(response, '/neither/')

    def test_neither_button_not_shown_in_step2(self):
        config = AdminConfig.objects.first()
        config.current_step = 2
        config.save()
        opt_a = Option.objects.create(text="Alex")
        opt_b = Option.objects.create(text="Pablo")
        Choice.objects.create(selected=opt_a, rejected=opt_b, step=1)
        Choice.objects.create(selected=opt_b, rejected=opt_a, step=1)
        response = self.client.get('/')
        self.assertNotContains(response, '/neither/')


class CompleteViewRedirectTest(TestCase):
    def setUp(self):
        AdminConfig.objects.create(prompt="test", current_step=1, rounds_count=5)

    def test_redirects_to_main_when_session_incomplete(self):
        session = self.client.session
        session.save()
        UserSession.objects.create(session_key=session.session_key, is_completed=False)
        mock_adapter = MagicMock()
        mock_adapter.generate_options.return_value = ("A", "B")
        with patch('selector.views.get_llm_adapter', return_value=mock_adapter):
            response = self.client.get('/complete/')
            self.assertRedirects(response, '/')

    def test_redirects_to_main_when_step_changed(self):
        session = self.client.session
        session.save()
        UserSession.objects.create(
            session_key=session.session_key,
            is_completed=True,
            step_completed=1
        )
        config = AdminConfig.objects.first()
        config.current_step = 2
        config.save()
        opt_a = Option.objects.create(text="A")
        opt_b = Option.objects.create(text="B")
        Choice.objects.create(selected=opt_a, rejected=opt_b, step=1)
        Choice.objects.create(selected=opt_b, rejected=opt_a, step=1)
        response = self.client.get('/complete/')
        self.assertRedirects(response, '/')

    def test_stays_on_complete_when_valid(self):
        session = self.client.session
        session.save()
        UserSession.objects.create(
            session_key=session.session_key,
            is_completed=True,
            step_completed=1
        )
        response = self.client.get('/complete/')
        self.assertEqual(response.status_code, 200)
