from django.views.generic.base import TemplateResponseMixin, View
from django.http import HttpResponseRedirect
#from django.forms.models import BaseInlineFormSet

from mongogeneric.list import MultipleDocumentsMixin, MultipleDocumentsTemplateResponseMixin
from mongogeneric.compat import ContextMixin
from mongodbforms import documentformset_factory, inlineformset_factory


class BaseFormSetMixin(object):
    """
    Base class for constructing a FormSet within a view
    """
    document = None
    initial = []
    form_class = None
    formset_class = None
    success_url = None
    extra = 2
    max_num = None
    can_order = False
    can_delete = False
    
    def construct_formset(self):
        return self.get_formset()(initial=self.get_initial(), **self.get_formset_kwargs())

    def get_initial(self):
        return self.initial

    def get_formset_class(self):
        return self.formset_class

    def get_form_class(self):
        return self.form_class

    def get_formset(self):
        return documentformset_factory(self.document, self.get_form_class(), **self.get_factory_kwargs())
     
    def get_formset_kwargs(self):
        kwargs = {}
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
                'files': self.request.FILES,
            })
        return kwargs
    
    def get_factory_kwargs(self):
        kwargs = {
            'extra': self.extra,
            'max_num': self.max_num,
            'can_order': self.can_order,
            'can_delete': self.can_delete,
        }
        
        if self.get_formset_class():
            kwargs['formset'] = self.get_formset_class()
        
        return kwargs 


class FormSetMixin(BaseFormSetMixin, ContextMixin):
    """
    A mixin that provides a way to show and handle a formset in a request.
    """

    def get_success_url(self):
        """
        Returns the supplied URL.
        """
        if self.success_url:
            url = self.success_url
        else:
            # Default to returning to the same page
            url = self.request.get_full_path()
        return url

    def formset_valid(self, formset):
        """
        If the formset is valid redirect to the supplied URL
        """
        return HttpResponseRedirect(self.get_success_url())

    def formset_invalid(self, formset):
        """
        If the formset is invalid, re-render the context data with the
        data-filled formset and errors.
        """
        return self.render_to_response(self.get_context_data(formset=formset))


class DocumentFormSetMixin(FormSetMixin, MultipleDocumentsMixin):
    """
    A mixin that provides a way to show and handle a document formset in a request.
    """

    exclude = None
    fields = None
    formfield_callback = None

    def get_context_data(self, **kwargs):
        """
        If an object list has been supplied, inject it into the context with the
        supplied context_object_name name.
        """
        context = {}

        if self.object_list:
            context['object_list'] = self.object_list
            context_object_name = self.get_context_object_name(self.object_list)
            if context_object_name:
                context[context_object_name] = self.object_list
        context.update(kwargs)

        # MultipleObjectMixin get_context_data() doesn't work when object_list
        # is not provided in kwargs, so we skip MultipleObjectMixin and call
        # ContextMixin directly.
        return ContextMixin.get_context_data(self, **context)

    def get_formset_kwargs(self):
        """
        Returns the keyword arguments for instantiating the formset.
        """
        kwargs = super(DocumentFormSetMixin, self).get_formset_kwargs()
        kwargs['queryset'] = self.get_queryset()
        return kwargs

    def get_factory_kwargs(self):
        """
        Returns the keyword arguments for calling the formset factory
        """
        kwargs = super(DocumentFormSetMixin, self).get_factory_kwargs()
        kwargs.update({
            'exclude': self.exclude,
            'fields': self.fields,
            'formfield_callback': self.formfield_callback,
        })
        if self.get_form_class():
            kwargs['form'] = self.get_form_class()
        if self.get_formset_class():
            kwargs['formset'] = self.get_formset_class()
        return kwargs

    def get_formset(self):
        """
        Returns the formset class from the document formset factory
        """
        return documentformset_factory(self.document, **self.get_factory_kwargs())

    def formset_valid(self, formset):
        """
        If the formset is valid, save the associated documents.
        """
        self.object_list = formset.save()
        return super(DocumentFormSetMixin, self).formset_valid(formset)


class ProcessFormSetView(View):
    """
    A mixin that processes a formset on POST.
    """

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests and instantiates a blank version of the formset.
        """
        formset = self.construct_formset()
        return self.render_to_response(self.get_context_data(formset=formset))

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a formset instance with the passed
        POST variables and then checked for validity.
        """
        formset = self.construct_formset()
        if formset.is_valid():
            return self.formset_valid(formset)
        else:
            return self.formset_invalid(formset)

    # PUT is a valid HTTP verb for creating (with a known URL) or editing an
    # object, note that browsers only support POST for now.
    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)


class BaseFormSetView(FormSetMixin, ProcessFormSetView):
    """
    A base view for displaying a formset
    """


class FormSetView(TemplateResponseMixin, BaseFormSetView):
    """
    A view for displaying a formset, and rendering a template response
    """


class BaseDocumentFormSetView(DocumentFormSetMixin, ProcessFormSetView):
    """
    A base view for displaying a document formset
    """
    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        return super(BaseDocumentFormSetView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        return super(BaseDocumentFormSetView, self).post(request, *args, **kwargs)


class DocumentFormSetView(MultipleDocumentsTemplateResponseMixin, BaseDocumentFormSetView):
    """
    A view for displaying a document formset, and rendering a template response
    """
