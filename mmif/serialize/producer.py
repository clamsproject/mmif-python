"""
The :mod:`producer` module contains the producer context, the write mode of a
MMIF. See :meth:`mmif.serialize.mmif.Mmif.set_producer`.
"""

import copy
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional, Union, cast

from mmif.serialize.view import View
from mmif.vocabulary import AnnotationTypes

if TYPE_CHECKING:
    from mmif.serialize.mmif import Mmif

__all__ = ['EmptyOutputWarning', 'ProducerContext']


class EmptyOutputWarning(UserWarning):
    """
    Issued when a run leaves no view: it produced no annotations, no error,
    and no warnings.
    """


class ProducerContext:
    """
    The write mode of a MMIF, for one run of a producer. Holds what the run
    needs to know: a snapshot taken when the producer is set, the signature,
    and the warnings raised during the run.

    While a producer is set, views that existed when it was set are serialized
    as they are in memory, and :meth:`mmif.serialize.mmif.Mmif.serialize`
    finalizes the views of the run in its output: capital ``Annotation``
    records, factored properties, ``contains`` pruning, removal of empty
    views, and one run ID. The ``Mmif`` object itself does not change, so
    repeated serialization gives the same output.

    Leaving the ``with`` block turns the mode off. An exception propagates
    unchanged.

    :param mmif: the MMIF the run works on
    :param signature: a view whose metadata is signed by the producer, copied
        to the views this context writes
    :raises RuntimeError: if a producer is already set on the MMIF
    """

    def __init__(self, mmif: 'Mmif', signature: View) -> None:
        if mmif._producer is not None:
            raise RuntimeError('A producer is already set on this MMIF.')
        self.mmif = mmif
        self.signature = signature
        self._warnings: list[Warning] = []
        self._view_metadata: dict[str, Any] = {}
        self._run_id: Optional[datetime] = None
        self._existing_view_ids = {view.id for view in mmif.views}
        self._entry_pending = {doc.id: dict(doc._props_pending.items())
                               for doc in self._documents()}
        mmif._producer = self

    def __enter__(self) -> 'ProducerContext':
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> bool:
        self.mmif._producer = None
        return False

    def add_warnings(self,
                     *issued: Union[Warning, warnings.WarningMessage]) -> None:
        """
        Records warnings of this run, written to one signed warnings view.

        :param issued: warnings, as raised or as caught by
            ``warnings.catch_warnings(record=True)``
        """
        for warning in issued:
            if isinstance(warning, warnings.WarningMessage):
                # `warnings.warn()` turns a str message into a Warning
                warning = cast(Warning, warning.message)
            self._warnings.append(warning)

    def set_view_metadata(self, key: str, value: Any) -> None:
        """
        Sets an additional metadata property on every view of this run,
        including the views this context writes (e.g., ``appProfiling``).

        :param key: the metadata key
        :param value: the value
        """
        self._view_metadata[key] = value

    def _finalize_output(self, views_out: list[dict],
                         include_context: bool) -> None:
        """
        Finalizes the views of this run in a serialized MMIF. Earlier views
        are not touched.

        :param views_out: serialized views, changed in place
        :param include_context: See :meth:`mmif.serialize.mmif.Mmif.serialize`.
        """
        if self._run_id is None:
            self._run_id = self._find_run_id()
        plan = self._plan_capital_annotations(views_out, include_context)
        self.mmif._write_capital_annotations(plan, views_out, include_context)
        run_views_out = [view_out for view_out in views_out
                         if view_out['id'] not in self._existing_view_ids]
        self.mmif._factor_out_in_output(run_views_out)
        self.mmif._prune_contains_in_output(run_views_out)

        empty_ids = {view_out['id'] for view_out in run_views_out
                     if self._is_empty(view_out)}
        views_out[:] = [view_out for view_out in views_out
                        if view_out['id'] not in empty_ids]
        run_views_out = [view_out for view_out in run_views_out
                         if view_out['id'] not in empty_ids]

        run_warnings = list(self._warnings)
        if not run_views_out:
            run_warnings.append(EmptyOutputWarning(
                f'App "{self.signature.metadata.app}" produced no annotations '
                f'for this input; the input may lack expected content, or '
                f'there may genuinely be nothing to annotate.'))
        if run_warnings:
            warnings_view = self._new_signed_view(views_out)
            warnings_view.metadata.add_warnings(*run_warnings)
            warnings_out = warnings_view._serialize(
                include_context=include_context)
            views_out.append(warnings_out)
            run_views_out.append(warnings_out)

        for view_out in run_views_out:
            view_out['metadata'].update(self._view_metadata)
            if include_context:
                view_out['metadata']['timestamp'] = self._run_id

    def _find_run_id(self) -> datetime:
        """
        Finds the run ID: the timestamp of the first view of this run, which
        ``Mmif.new_view()`` assigned. A run that created no view gets the
        current time.

        :return: the run ID
        """
        return next((view.metadata.timestamp for view in self.mmif.views
                     if view.id not in self._existing_view_ids
                     and view.metadata.timestamp is not None),
                    datetime.now(timezone.utc))

    def _plan_capital_annotations(
            self, views_out: list[dict], include_context: bool,
    ) -> list[tuple[View, str, dict, bool]]:
        """
        Decides where the pending properties of this run are recorded: those
        that weren't pending on entry and that no view already records. A
        document created in this run takes them itself, and the others get
        records in the last view of this run. A signed view is added to the
        output when the run created no view to hold the records.

        :param views_out: serialized views, changed when a view is added
        :param include_context: See :meth:`mmif.serialize.mmif.Mmif.serialize`.
        :return: the plan, in the form that
            :meth:`mmif.serialize.mmif.Mmif._write_capital_annotations` takes
        """
        recorded = defaultdict(dict)
        for view in self.mmif.views:
            for ann in view.get_annotations(AnnotationTypes.Annotation):
                recorded[ann.get('document')].update(
                    ann._resolved_properties())

        run_views = [view for view in self.mmif.views
                     if view.id not in self._existing_view_ids]
        doc_views = {doc.id: view for view in run_views
                     for doc in view.get_documents()}
        target = next((view for view in reversed(run_views)
                       if not view.has_error() and not view.has_warnings()),
                      None)

        plan = []
        for doc in self._documents():
            on_entry = self._entry_pending.get(doc.id, {})
            props = {key: value for key, value in doc._props_pending.items()
                     if key != 'id'
                     and not (key in on_entry and on_entry[key] == value)
                     and not (key in recorded[doc.id]
                              and recorded[doc.id][key] == value)}
            if not props:
                continue
            if doc.id in doc_views:
                plan.append((doc_views[doc.id], doc.id, props, True))
                continue
            if target is None:
                target = self._new_signed_view(views_out)
                views_out.append(
                    target._serialize(include_context=include_context))
            plan.append((target, doc.id, props, False))
        return plan

    def _documents(self):
        """
        Iterates over all documents, in the top-level list and in the views.
        """
        yield from self.mmif.documents
        for view in self.mmif.views:
            yield from view.get_documents()

    def _new_signed_view(self, views_out: list[dict]) -> View:
        """
        Creates a view for the output only, with an ID that is free in the
        output and in the object, and with the metadata of the signature.

        :param views_out: serialized views
        :return: the new view, not added to the MMIF
        """
        used_ids = {view_out['id'] for view_out in views_out}
        used_ids.update(view.id for view in self.mmif.views)
        index = len(used_ids)
        while f'{self.mmif.view_prefix}{index}' in used_ids:
            index += 1
        view = View()
        view.id = f'{self.mmif.view_prefix}{index}'
        view.metadata = copy.deepcopy(self.signature.metadata)
        return view

    @staticmethod
    def _is_empty(view_out: dict) -> bool:
        """
        Checks that a serialized view has no annotations, no error, and no
        warnings.

        :param view_out: a serialized view
        :return: True for an empty view
        """
        metadata = view_out['metadata']
        return not (view_out['annotations'] or metadata.get('error')
                    or metadata.get('warnings'))
