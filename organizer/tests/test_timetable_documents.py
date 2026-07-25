from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from organizer.core import paths
from organizer.models import TimetableDocument

from .helpers import SandboxedPathsTestCase

_MINIMAL_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def _pdf_upload(name="exam-timetable.pdf", content=_MINIMAL_PDF):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class TimetableDocumentUploadViewTests(SandboxedPathsTestCase):
    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("timetable_document_upload"))
        self.assertEqual(response.status_code, 405)

    def test_without_an_active_profile_redirects_without_uploading(self):
        response = self.client.post(reverse("timetable_document_upload"), {"file": _pdf_upload()})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(TimetableDocument.objects.exists())

    def test_uploads_a_pdf_under_the_profiles_own_folder(self):
        profile = self.make_profile()

        response = self.client.post(reverse("timetable_document_upload"), {
            "kind": "examination", "title": "Sem 2 exams", "file": _pdf_upload(),
        })

        self.assertRedirects(response, reverse("timetable_view"))
        document = TimetableDocument.objects.get()
        self.assertEqual(document.profile, profile)
        self.assertEqual(document.kind, "examination")
        self.assertEqual(document.title, "Sem 2 exams")
        stored = Path(document.file_path)
        self.assertTrue(stored.exists())
        self.assertTrue(stored.is_relative_to(paths.timetable_documents_dir(profile.root_path)))
        self.assertEqual(stored.read_bytes(), _MINIMAL_PDF)

    def test_defaults_title_to_the_filename_when_left_blank(self):
        self.make_profile()
        self.client.post(reverse("timetable_document_upload"), {
            "kind": "other", "file": _pdf_upload("my exam sched.pdf"),
        })
        self.assertEqual(TimetableDocument.objects.get().title, "my exam sched")

    def test_rejects_a_non_pdf_extension(self):
        self.make_profile()
        upload = SimpleUploadedFile("notes.txt", b"not a pdf", content_type="text/plain")

        response = self.client.post(reverse("timetable_document_upload"), {"kind": "other", "file": upload})

        self.assertRedirects(response, reverse("timetable_view"))
        self.assertFalse(TimetableDocument.objects.exists())

    def test_rejects_a_pdf_named_file_that_is_not_really_a_pdf(self):
        self.make_profile()
        upload = SimpleUploadedFile("fake.pdf", b"not actually a pdf", content_type="application/pdf")

        response = self.client.post(reverse("timetable_document_upload"), {"kind": "other", "file": upload})

        self.assertRedirects(response, reverse("timetable_view"))
        self.assertFalse(TimetableDocument.objects.exists())

    def test_rejects_an_oversized_file(self):
        self.make_profile()
        from organizer.views import integrations as integrations_views

        oversized = _MINIMAL_PDF + b"0" * 1024
        upload = _pdf_upload(content=oversized)

        with mock.patch.object(integrations_views, "_MAX_TIMETABLE_DOC_BYTES", len(_MINIMAL_PDF)):
            response = self.client.post(reverse("timetable_document_upload"), {"kind": "other", "file": upload})

        self.assertRedirects(response, reverse("timetable_view"))
        self.assertFalse(TimetableDocument.objects.exists())


class TimetableDocumentDownloadViewTests(SandboxedPathsTestCase):
    def test_serves_the_stored_bytes(self):
        profile = self.make_profile()
        self.client.post(reverse("timetable_document_upload"), {"kind": "other", "file": _pdf_upload()})
        document = TimetableDocument.objects.get()

        response = self.client.get(reverse("timetable_document_download", args=[document.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response.content, _MINIMAL_PDF)

    def test_another_profiles_document_404s(self):
        profile = self.make_profile()
        other = self.make_profile(name="Other", is_active=False)
        document = TimetableDocument.objects.create(
            profile=other, kind="other", title="Theirs",
            original_filename="x.pdf", file_path=str(self.profile_root / "x.pdf"),
        )

        response = self.client.get(reverse("timetable_document_download", args=[document.pk]))
        self.assertEqual(response.status_code, 404)


class TimetableDocumentDeleteViewTests(SandboxedPathsTestCase):
    def test_get_is_not_allowed(self):
        profile = self.make_profile()
        document = TimetableDocument.objects.create(
            profile=profile, kind="other", title="x", original_filename="x.pdf",
            file_path=str(self.profile_root / "x.pdf"),
        )
        response = self.client.get(reverse("timetable_document_delete", args=[document.pk]))
        self.assertEqual(response.status_code, 405)

    def test_deletes_the_row_and_the_file_on_disk(self):
        profile = self.make_profile()
        self.client.post(reverse("timetable_document_upload"), {"kind": "other", "file": _pdf_upload()})
        document = TimetableDocument.objects.get()
        stored = Path(document.file_path)
        self.assertTrue(stored.exists())

        response = self.client.post(reverse("timetable_document_delete", args=[document.pk]))

        self.assertRedirects(response, reverse("timetable_view"))
        self.assertFalse(TimetableDocument.objects.exists())
        self.assertFalse(stored.exists())
