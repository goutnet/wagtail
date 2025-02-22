# Generated by Django 3.2.6 on 2022-11-09 07:50

import datetime
import logging

import django.core.serializers.json
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone, dateparse

logger = logging.getLogger("wagtail.migrations")


def legacy_to_iso_format(date_string, tz=None):
    dt = datetime.datetime.strptime(date_string, "%d %b %Y %H:%M")
    if settings.USE_TZ:
        dt = timezone.make_aware(dt, datetime.timezone.utc if tz is None else tz)
        dt = timezone.localtime(dt, datetime.timezone.utc)
    # We return the datetime object, so DjangoJSONEncoder will serialize it accordingly.
    return dt


def iso_to_legacy_format(date_string, tz=None):
    dt = dateparse.parse_datetime(date_string)
    if dt is None:
        raise ValueError("date isn't well formatted")
    if settings.USE_TZ:
        dt = timezone.localtime(dt, datetime.timezone.utc if tz is None else tz)
    return dt.strftime("%d %b %Y %H:%M")


def migrate_logs_with_created_only(model, converter):
    for item in (
        model.objects.filter(
            action__in=["wagtail.revert", "wagtail.rename", "wagtail.publish"]
        )
        .only("data")
        .iterator()
    ):
        try:
            # If a previous_revision was available, the data contains "revision" with
            # its created date.
            # Also, there are "wagtail.publish" logs, which don't set data at all.
            created = item.data["revision"]["created"]
            # "created" is set to the previous revision's created_at, which is set
            # to UTC by django.
            item.data["revision"]["created"] = converter(created)
        except ValueError:
            logger.warning(
                "Failed to migrate 'created' timestamp '%s' of %s %s (%s)",
                item.data["revision"]["created"],
                model.__name__,
                item.pk,
                converter.__name__,
            )
            continue
        except KeyError:
            continue
        else:
            item.save(update_fields=["data"])


def migrate_schedule_logs(model, converter):
    for item in (
        model.objects.filter(
            action__in=["wagtail.publish.schedule", "wagtail.schedule.cancel"]
        )
        .only("data")
        .iterator()
    ):
        created = item.data["revision"]["created"]
        # May be unset for "wagtail.schedule.cancel"-logs.
        go_live_at = item.data["revision"].get("go_live_at")
        changed = False
        try:
            # "created" is set to timezone.now() for new revisions ("wagtail.publish.schedule")
            # and to self.created_at for "wagtail.schedule.cancel", which is set to UTC
            # by django.
            item.data["revision"]["created"] = converter(created)
            changed = True
        except ValueError:
            logger.warning(
                "Failed to migrate 'created' timestamp '%s' of %s %s (%s)",
                created,
                model.__name__,
                item.pk,
                converter.__name__,
            )

        if go_live_at:
            # The go_live_at date is set to the revision object's "go_live_at".
            # The revision's object is created by deserializing the json data (see wagtail.models.Revision.as_object()),
            # and this process converts all datetime objects to the local timestamp (see https://github.com/wagtail/django-modelcluster/blob/8666f16eaf23ca98afc160b0a4729864411c0563/modelcluster/models.py#L109-L115).
            # That's the reason, why this date is the only date, which is not stored in the log's JSON as UTC, but in the default timezone.
            try:
                item.data["revision"]["go_live_at"] = converter(
                    go_live_at, tz=timezone.get_default_timezone()
                )
                changed = True
            except ValueError:
                logger.warning(
                    "Failed to migrate 'go_live_at' timestamp '%s' of %s %s (%s)",
                    go_live_at,
                    model.__name__,
                    item.pk,
                    converter.__name__,
                )

        if changed:
            item.save(update_fields=["data"])


def migrate_custom_to_iso_format(apps, schema_editor):
    ModelLogEntry = apps.get_model("wagtailcore.ModelLogEntry")
    PageLogEntry = apps.get_model("wagtailcore.PageLogEntry")

    migrate_logs_with_created_only(ModelLogEntry, legacy_to_iso_format)
    migrate_logs_with_created_only(PageLogEntry, legacy_to_iso_format)

    migrate_schedule_logs(ModelLogEntry, legacy_to_iso_format)
    migrate_schedule_logs(PageLogEntry, legacy_to_iso_format)


def migrate_iso_to_custom_format(apps, schema_editor):
    ModelLogEntry = apps.get_model("wagtailcore.ModelLogEntry")
    PageLogEntry = apps.get_model("wagtailcore.PageLogEntry")

    migrate_logs_with_created_only(ModelLogEntry, iso_to_legacy_format)
    migrate_logs_with_created_only(PageLogEntry, iso_to_legacy_format)

    migrate_schedule_logs(ModelLogEntry, iso_to_legacy_format)
    migrate_schedule_logs(PageLogEntry, iso_to_legacy_format)


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailcore", "0087_alter_grouppagepermission_unique_together_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="modellogentry",
            name="data",
            field=models.JSONField(
                blank=True,
                default=dict,
                encoder=django.core.serializers.json.DjangoJSONEncoder,
            ),
        ),
        migrations.AlterField(
            model_name="pagelogentry",
            name="data",
            field=models.JSONField(
                blank=True,
                default=dict,
                encoder=django.core.serializers.json.DjangoJSONEncoder,
            ),
        ),
        migrations.RunPython(
            migrate_custom_to_iso_format,
            migrate_iso_to_custom_format,
        ),
    ]
