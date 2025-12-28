from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from selector.models import Option, Choice


class UnduplicateCommandTest(TestCase):
    def test_command_exists(self):
        out = StringIO()
        call_command('unduplicate_options', '--dry-run', stdout=out)

    def test_normalizes_option_text(self):
        Option.objects.create(text='  option one  ')
        call_command('unduplicate_options', stdout=StringIO())
        option = Option.objects.first()
        self.assertEqual(option.text, 'OPTION ONE')

    def test_merges_duplicates_to_oldest_option(self):
        opt1 = Option.objects.create(text='option')
        opt2 = Option.objects.create(text='OPTION')
        opt3 = Option.objects.create(text='  option  ')
        call_command('unduplicate_options', stdout=StringIO())
        with self.subTest('should keep only one option'):
            self.assertEqual(Option.objects.count(), 1)
        with self.subTest('should keep oldest option'):
            self.assertTrue(Option.objects.filter(id=opt1.id).exists())
        with self.subTest('should delete duplicates'):
            self.assertFalse(Option.objects.filter(id=opt2.id).exists())
            self.assertFalse(Option.objects.filter(id=opt3.id).exists())

    def test_updates_selected_choice_references(self):
        opt1 = Option.objects.create(text='option')
        opt2 = Option.objects.create(text='OPTION')
        opt_other = Option.objects.create(text='other')
        choice = Choice.objects.create(selected=opt2, rejected=opt_other)
        call_command('unduplicate_options', stdout=StringIO())
        choice.refresh_from_db()
        self.assertEqual(choice.selected, opt1)

    def test_updates_rejected_choice_references(self):
        opt1 = Option.objects.create(text='option')
        opt2 = Option.objects.create(text='OPTION')
        opt_other = Option.objects.create(text='other')
        choice = Choice.objects.create(selected=opt_other, rejected=opt2)
        call_command('unduplicate_options', stdout=StringIO())
        choice.refresh_from_db()
        self.assertEqual(choice.rejected, opt1)

    def test_dry_run_does_not_modify_database(self):
        opt1 = Option.objects.create(text='option')
        opt2 = Option.objects.create(text='OPTION')
        call_command('unduplicate_options', '--dry-run', stdout=StringIO())
        with self.subTest('should not delete duplicates'):
            self.assertEqual(Option.objects.count(), 2)
        with self.subTest('should not normalize text'):
            opt1.refresh_from_db()
            self.assertEqual(opt1.text, 'option')

    def test_outputs_merge_information(self):
        opt1 = Option.objects.create(text='option')
        opt2 = Option.objects.create(text='OPTION')
        opt3 = Option.objects.create(text='  option  ')
        out = StringIO()
        call_command('unduplicate_options', stdout=out)
        output = out.getvalue()
        with self.subTest('should output merge of opt2 to opt1'):
            self.assertIn(f'{opt2.id}', output)
            self.assertIn(f'{opt1.id}', output)
        with self.subTest('should output merge of opt3 to opt1'):
            self.assertIn(f'{opt3.id}', output)

    def test_dry_run_outputs_merge_preview(self):
        opt1 = Option.objects.create(text='option')
        opt2 = Option.objects.create(text='OPTION')
        out = StringIO()
        call_command('unduplicate_options', '--dry-run', stdout=out)
        output = out.getvalue()
        with self.subTest('should output preview'):
            self.assertIn(f'{opt2.id}', output)
            self.assertIn(f'{opt1.id}', output)
