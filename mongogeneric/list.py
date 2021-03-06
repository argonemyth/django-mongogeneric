from django.core.paginator import Paginator, InvalidPage
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.utils.encoding import smart_str
from django.utils.translation import ugettext as _
from django.views.generic.base import TemplateResponseMixin, View

from mongodbforms.util import get_document_options


class MultipleDocumentsMixin(object):
    allow_empty = True
    queryset = None
    document = None
    paginate_by = None
    context_object_name = None
    paginator_class = Paginator

    def get_queryset(self):
        """
        Get the list of items for this view. This must be an interable, and may
        be a queryset (in which qs-specific behavior will be enabled).
        """
        if self.queryset is not None:
            queryset = self.queryset
            queryset = queryset.clone()
        elif self.document is not None:
            queryset = self.document.objects()
        else:
            raise ImproperlyConfigured("'%s' must define 'queryset' or 'document'"
                                       % self.__class__.__name__)
        return queryset

    def paginate_queryset(self, queryset, page_size):
        """
        Paginate the queryset, if needed.
        """
        paginator = self.get_paginator(queryset, page_size, allow_empty_first_page=self.get_allow_empty())
        page = self.kwargs.get('page') or self.request.GET.get('page') or 1
        try:
            page_number = int(page)
        except ValueError:
            if page == 'last':
                page_number = paginator.num_pages
            else:
                raise Http404(_("Page is not 'last', nor can it be converted to an int."))
        try:
            page = paginator.page(page_number)
            return (paginator, page, page.object_list, page.has_other_pages())
        except InvalidPage:
            raise Http404(_('Invalid page (%(page_number)s)') % {
                                'page_number': page_number
            })

    def get_paginate_by(self, queryset):
        """
        Get the number of items to paginate by, or ``None`` for no pagination.
        """
        return self.paginate_by

    def get_paginator(self, queryset, per_page, orphans=0, allow_empty_first_page=True):
        """
        Return an instance of the paginator for this view.
        """
        return self.paginator_class(queryset, per_page, orphans=orphans, allow_empty_first_page=allow_empty_first_page)

    def get_allow_empty(self):
        """
        Returns ``True`` if the view should display empty lists, and ``False``
        if a 404 should be raised instead.
        """
        return self.allow_empty

    def get_context_object_name(self, object_list):
        """
        Get the name of the item to be used in the context.
        """
        if self.context_object_name:
            return self.context_object_name
        elif hasattr(object_list, '_document'):
            opts = get_document_options(object_list._document)
            return smart_str('%s_list' % opts.object_name.lower())
        else:
            return None

    def get_context_data(self, **kwargs):
        """
        Get the context for this view.
        """
        queryset = kwargs.pop('object_list')
        page_size = self.get_paginate_by(queryset)
        context_object_name = self.get_context_object_name(queryset)
        if page_size:
            paginator, page, queryset, is_paginated = self.paginate_queryset(queryset, page_size)
            context = {
                'paginator': paginator,
                'page_obj': page,
                'is_paginated': is_paginated,
                'object_list': queryset
            }
        else:
            context = {
                'paginator': None,
                'page_obj': None,
                'is_paginated': False,
                'object_list': queryset
            }
        context.update(kwargs)
        if context_object_name is not None:
            context[context_object_name] = queryset
        return context


class BaseListView(MultipleDocumentsMixin, View):
    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        allow_empty = self.get_allow_empty()
        if not allow_empty and len(self.object_list) == 0:
            raise Http404(_("Empty list and '%(class_name)s.allow_empty' is False.")
                          % {'class_name': self.__class__.__name__})
        context = self.get_context_data(object_list=self.object_list)
        return self.render_to_response(context)


class MultipleDocumentsTemplateResponseMixin(TemplateResponseMixin):
    template_name_suffix = '_list'

    def get_template_names(self):
        """
        Return a list of template names to be used for the request. Must return
        a list. May not be called if get_template is overridden.
        """
        try:
            names = super(MultipleDocumentsTemplateResponseMixin, self).get_template_names()
        except ImproperlyConfigured:
            # If template_name isn't specified, it's not a problem --
            # we just start with an empty list.
            names = []

        # If the list is a queryset, we'll invent a template name based on the
        # app and document name. This name gets put at the end of the template
        # name list so that user-supplied names override the automatically-
        # generated ones.
        if hasattr(self.object_list, '_document'):
            opts = get_document_options(self.object_list._document)
            names.append("%s/%s%s.html" % (opts.app_label, opts.object_name.lower(), self.template_name_suffix))

        return names


class ListView(MultipleDocumentsTemplateResponseMixin, BaseListView):
    """
    Render some list of objects, set by `self.document` or `self.queryset`.
    `self.queryset` can actually be any iterable of items, not just a queryset.
    """
    
