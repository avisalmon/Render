from django.db.models import Q
from rest_framework import serializers

from .grooves import check_groove
from .models import ChordQuality, ChordScale, Completion, DrillAttempt, Exercise, Lesson, Phrase, Player, PracticeSession, Progression, Scale, ScaleFingering, ScaleRun, Style, Tag, Take
from .teaching import check_notes


class RankedScaleSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(source="scale.slug")
    name = serializers.CharField(source="scale.name")
    intervals = serializers.JSONField(source="scale.intervals")

    class Meta:
        model = ChordScale
        fields = ["slug", "name", "intervals", "preference", "note"]


class ChordQualitySerializer(serializers.ModelSerializer):
    scales = serializers.SerializerMethodField()

    class Meta:
        model = ChordQuality
        fields = ["id", "symbol", "name", "family", "intervals", "roles", "aliases", "sort_order", "scales"]

    def get_scales(self, obj):
        ranked = sorted(obj.chord_scales.all(), key=lambda cs: cs.preference)
        return RankedScaleSerializer(ranked, many=True).data


class ScaleSerializer(serializers.ModelSerializer):
    parent_slug = serializers.SlugField(source="parent_scale.slug", default=None, read_only=True)

    class Meta:
        model = Scale
        fields = ["id", "slug", "name", "family", "intervals", "parent_slug", "mode_number"]


class ScaleFingeringSerializer(serializers.ModelSerializer):
    scale = serializers.SlugRelatedField(slug_field="slug", read_only=True)

    class Meta:
        model = ScaleFingering
        fields = ["id", "scale", "root_pc", "hand", "first_octave", "next_octaves", "last_note", "authorship"]


class ChordScaleSerializer(serializers.ModelSerializer):
    quality_symbol = serializers.CharField(source="chord_quality.symbol", read_only=True)
    scale_slug = serializers.CharField(source="scale.slug", read_only=True)

    class Meta:
        model = ChordScale
        fields = ["id", "chord_quality", "quality_symbol", "scale", "scale_slug", "preference", "note"]


# ---------------------------------------------------------------- SPR-I.2.2


class VisibleStyleField(serializers.PrimaryKeyRelatedField):
    """A style I may point a progression at: a preset, or one of mine."""

    def get_queryset(self):
        user = self.context["request"].user
        return Style.objects.filter(Q(is_preset=True) | Q(owner=user))


class TagSerializer(serializers.ModelSerializer):
    progressions = serializers.IntegerField(source="progression_count", read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "progressions"]


class OwnedSerializer(serializers.ModelSerializer):
    """Presets and a player's own rows travel in the same shape. Who owns a row is
    told as `is_mine`; the player's id never leaves the server."""

    is_mine = serializers.SerializerMethodField()

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and obj.owner_id and obj.owner_id == request.user.pk)


class StyleSerializer(OwnedSerializer):
    class Meta:
        model = Style
        fields = [
            "id", "name", "slug", "genre", "feel", "swing_ratio", "time_signature",
            "default_tempo", "min_tempo", "max_tempo", "drums", "bass", "comp",
            "is_preset", "is_mine",
        ]  # fmt: skip
        read_only_fields = ["slug", "is_preset"]

    def validate(self, attrs):
        # Partial updates carry only some fields; judge the whole groove as it will be saved.
        def value(name):
            return attrs[name] if name in attrs else getattr(self.instance, name, None)

        problems = {}
        for field, message in check_groove(
            value("time_signature"), value("drums"), value("bass"), value("comp")
        ).items():
            problems[field] = [message]
        low, mid, high = value("min_tempo"), value("default_tempo"), value("max_tempo")
        if None not in (low, mid, high) and not low <= mid <= high:
            problems["default_tempo"] = ["The default tempo has to sit between the minimum and the maximum."]
        if problems:
            raise serializers.ValidationError(problems)
        return attrs


class ProgressionSerializer(OwnedSerializer):
    tags = serializers.SlugRelatedField(many=True, slug_field="slug", queryset=Tag.objects.all(), required=False)
    default_style = VisibleStyleField(required=False, allow_null=True)

    class Meta:
        model = Progression
        fields = [
            "id", "title", "slug", "genre", "tags", "chart", "home_key", "time_signature",
            "default_tempo", "default_style", "difficulty", "description",
            "is_preset", "is_mine", "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = ["slug", "is_preset", "created_at", "updated_at"]


class PlayerSerializer(serializers.ModelSerializer):
    """The player's own profile. `user` is read-only on purpose: the row is reached
    through the API as the person logged in, and nobody edits whose profile it is."""

    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Player
        fields = [
            "id", "username", "daily_goal_minutes", "latency_offset_ms", "midi_input_name",
            "note_names", "demo_output", "trainer_tempo", "timezone", "created_at",
        ]  # fmt: skip
        read_only_fields = ["created_at"]


class PracticeSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PracticeSession
        fields = ["id", "started_at", "ended_at", "active_seconds"]
        read_only_fields = ["started_at"]


class VisibleProgressionField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        user = self.context["request"].user
        return Progression.objects.filter(Q(is_preset=True) | Q(owner=user))


class OwnSessionField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return PracticeSession.objects.filter(player__user=self.context["request"].user)


class VisibleExerciseField(serializers.SlugRelatedField):
    """An exercise a take may be played for: a challenge, or one of a published lesson. The
    superuser who is reading the drafts may play those too."""

    def get_queryset(self):
        return visible_exercises(self.context["request"].user)


def visible_lessons(user):
    rows = Lesson.objects.all()
    return rows if user.is_superuser else rows.filter(status=Lesson.Status.PUBLISHED)


def visible_exercises(user):
    rows = Exercise.objects.select_related("lesson", "progression")
    return rows if user.is_superuser else rows.filter(Q(lesson__isnull=True) | Q(lesson__status=Lesson.Status.PUBLISHED))


class PhraseSerializer(OwnedSerializer):
    class Meta:
        model = Phrase
        fields = ["id", "name", "slug", "kind", "notes", "length_beats", "chart_context", "written_in_key", "is_preset", "is_mine"]
        read_only_fields = ["slug", "is_preset"]
        extra_kwargs = {"length_beats": {"coerce_to_string": False}}

    def validate(self, attrs):
        def value(name):
            return attrs[name] if name in attrs else getattr(self.instance, name, None)

        problem = check_notes(value("notes"), value("length_beats"))
        if problem:
            raise serializers.ValidationError({"notes": [problem]})
        return attrs


class LessonSerializer(serializers.ModelSerializer):
    progression_slug = serializers.CharField(source="progression.slug", default=None, read_only=True)
    prerequisite = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    exercises = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    exercises_done = serializers.SerializerMethodField()
    exercises_total = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            "id", "track", "order", "title", "slug", "level", "summary", "explanation", "demo_phrase",
            "progression", "progression_slug", "style", "prerequisite", "exercises", "authorship", "status",
            "state", "exercises_done", "exercises_total", "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = fields

    def _state(self, obj, key):
        return self.context.get("lesson_states", {}).get(obj.pk, {}).get(key)

    def get_state(self, obj):
        return self._state(obj, "state")

    def get_exercises_done(self, obj):
        return self._state(obj, "exercises_done")

    def get_exercises_total(self, obj):
        return self._state(obj, "exercises_total")

    def get_exercises(self, obj):
        return [e.slug for e in sorted(obj.exercises.all(), key=lambda e: (e.order, e.pk))]


class ExerciseSerializer(serializers.ModelSerializer):
    lesson = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    progression_slug = serializers.CharField(source="progression.slug", read_only=True)
    completed = serializers.SerializerMethodField()
    locked = serializers.SerializerMethodField()

    class Meta:
        model = Exercise
        fields = [
            "id", "slug", "lesson", "order", "title", "instructions", "progression", "progression_slug", "key",
            "tempo", "style", "bars", "scoring_kind", "scoring_params", "pass_score", "xp", "daily_eligible",
            "completed", "locked",
        ]  # fmt: skip
        read_only_fields = fields

    def get_completed(self, obj):
        return obj.pk in self.context.get("done_exercises", ())

    def get_locked(self, obj):
        if obj.lesson_id is None:
            return False
        return self.context.get("lesson_states", {}).get(obj.lesson_id, {}).get("state") == "locked"


class CompletionSerializer(serializers.ModelSerializer):
    exercise = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    exercise_title = serializers.CharField(source="exercise.title", read_only=True)
    lesson = serializers.CharField(source="exercise.lesson.slug", default=None, read_only=True)

    class Meta:
        model = Completion
        fields = ["id", "exercise", "exercise_title", "lesson", "take", "xp_awarded", "completed_at"]
        read_only_fields = fields


MOST_EVENTS = 20000


class TakeSerializer(serializers.ModelSerializer):
    """What the page posts after a take, checked for shape and range only. The server
    does not re-judge (data model, section 11): it believes the score for now, and it
    keeps the events so a later judge can disagree with a reason."""

    session = OwnSessionField()
    progression = VisibleProgressionField(required=False, allow_null=True)
    style = VisibleStyleField(required=False, allow_null=True)
    exercise = VisibleExerciseField(slug_field="slug", required=False, allow_null=True)
    completion = serializers.SerializerMethodField()

    class Meta:
        model = Take
        fields = [
            "id", "session", "progression", "style", "exercise", "chart", "home_key", "key", "time_signature", "tempo", "swing_ratio",
            "loop_from", "loop_to", "started_at", "duration_ms", "bars", "events", "score",
            "metrics", "judge_version", "is_kept", "completion", "created_at",
        ]  # fmt: skip
        read_only_fields = ["created_at", "completion"]

    def get_completion(self, obj):
        """What this take earned, if it was the one that passed the exercise. Only the server
        makes a completion, so there is nothing here the client can send."""
        done = getattr(obj, "completion", None)
        return {"id": done.pk, "xp_awarded": done.xp_awarded} if done else None

    def validate_events(self, events):
        if not isinstance(events, list):
            raise serializers.ValidationError("events is a list.")
        if len(events) > MOST_EVENTS:
            raise serializers.ValidationError(f"A take holds at most {MOST_EVENTS} events.")
        for i, e in enumerate(events):
            ok = (
                isinstance(e, dict)
                and isinstance(e.get("t_ms"), int) and not isinstance(e.get("t_ms"), bool)
                and e.get("type") in ("on", "off")
                and isinstance(e.get("note"), int) and 0 <= e["note"] <= 127
                and isinstance(e.get("velocity"), int) and 0 <= e["velocity"] <= 127
            )
            if not ok:
                raise serializers.ValidationError(f"event {i} is not {{t_ms, type: on/off, note 0..127, velocity 0..127}}.")
        return events

    def validate_metrics(self, metrics):
        if not isinstance(metrics, dict):
            raise serializers.ValidationError("metrics is an object.")
        return metrics

    def validate(self, attrs):
        def value(name):
            return attrs[name] if name in attrs else getattr(self.instance, name, None)

        if value("loop_to") is not None and value("loop_from") is not None and value("loop_to") <= value("loop_from"):
            raise serializers.ValidationError({"loop_to": ["loop_to has to be past loop_from."]})
        if value("bars") is not None and value("loop_to") is not None and value("loop_from") is not None:
            if value("bars") != value("loop_to") - value("loop_from"):
                raise serializers.ValidationError({"bars": ["bars has to be the number of bars between loop_from and loop_to."]})
        return attrs


# ---------------------------------------------------------------- SPR-I.8.2


class ScaleRunSerializer(serializers.ModelSerializer):
    """What the scales page posts after a run, checked for shape and range only. `passed` is the
    server's: the score measured against the pass line."""

    scale = serializers.SlugRelatedField(slug_field="slug", queryset=Scale.objects.all(), required=False)

    class Meta:
        model = ScaleRun
        fields = [
            "id", "scale", "root_pc", "octaves", "notes_per_beat", "tempo_bpm", "score", "pitch_accuracy", "timing_accuracy",
            "mean_offset_ms", "passed", "missed_steps", "judge_version", "created_at",
        ]  # fmt: skip
        read_only_fields = ["passed", "created_at"]

    def validate(self, attrs):
        if self.instance is None and "scale" not in attrs:
            major = Scale.objects.filter(slug="major").first()
            if major is None:
                raise serializers.ValidationError({"scale": ["The major scale is not seeded yet."]})
            attrs["scale"] = major
        return attrs


# ---------------------------------------------------------------- SPR-I.8.4


class DrillAttemptSerializer(serializers.ModelSerializer):
    """What the chords page posts for each prompt. `prompt` and `answer` are objects the page owns."""

    class Meta:
        model = DrillAttempt
        fields = [
            "id", "kind", "key_pc", "level", "prompt", "answer", "is_correct", "wrong_tries", "hint_used", "skipped",
            "response_ms", "answered_at",
        ]  # fmt: skip
        read_only_fields = ["answered_at"]

    def validate_prompt(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("prompt is an object.")
        return value

    def validate_answer(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("answer is an object.")
        return value

    def validate(self, attrs):
        def value(name):
            return attrs[name] if name in attrs else getattr(self.instance, name, None)

        if value("skipped") and value("response_ms") is not None:
            raise serializers.ValidationError({"response_ms": ["A skipped prompt has no response time."]})
        if value("skipped") and value("is_correct"):
            raise serializers.ValidationError({"is_correct": ["A skipped prompt is not correct."]})
        if value("is_correct") and value("wrong_tries"):
            raise serializers.ValidationError({"is_correct": ["A prompt with wrong tries is not correct."]})
        return attrs
