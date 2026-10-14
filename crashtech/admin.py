"""Admin registration for every model (building_an_app.md Rule 4).

Deliberately plain. The real screens are CrashTech's own; this is the
back door for the site owner, not a substitute for building the product.
"""

from django.contrib import admin

from . import models

for _model in (
    models.Hackathon, models.Milestone, models.EventRole, models.RoleInvitation,
    models.Registration, models.Team, models.TeamMembership,
    models.KitItem, models.KitIssue,
    models.ContentPage, models.ScheduleItem, models.Sponsor,
    models.Challenge, models.Deliverable,
    models.Submission, models.SubmissionFile, models.UploadToken,
    models.JudgeGrade, models.Certificate, models.MuseumPage, models.MuseumPhoto,
    models.Study, models.StudyReference, models.Questionnaire, models.Question,
    models.Response, models.Answer, models.ResearchConsent,
):
    admin.site.register(_model)
