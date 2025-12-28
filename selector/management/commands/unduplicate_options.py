from collections import defaultdict
from django.core.management.base import BaseCommand
from selector.models import Option, Choice


class Command(BaseCommand):
    help = 'Unduplicate Option records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        options_by_normalized = defaultdict(list)
        for option in Option.objects.all().order_by('created_at'):
            normalized = option.text.strip().upper()
            options_by_normalized[normalized].append(option)
        for normalized, option_list in options_by_normalized.items():
            preferred = option_list[0]
            duplicates = option_list[1:]
            for duplicate in duplicates:
                action = 'Would merge' if dry_run else 'Merging'
                self.stdout.write(f'{action} option {duplicate.id} into {preferred.id}')
                if not dry_run:
                    Choice.objects.filter(selected=duplicate).update(selected=preferred)
                    Choice.objects.filter(rejected=duplicate).update(rejected=preferred)
            if not dry_run:
                preferred.text = normalized
                preferred.save()
                for duplicate in duplicates:
                    duplicate.delete()
