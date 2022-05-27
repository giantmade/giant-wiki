from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator

from django.contrib.auth.models import User

from . import models, forms, documents


@login_required
def page(request, path="index", specific_id=False):
    """
    This displays a given wiki page.
    """

    # Get the sidebar.
    try:
        sidebar = models.Page.objects.filter(path="Sidebar").order_by("-last_updated")[0]
    except (models.Page.DoesNotExist, IndexError):
        sidebar = models.Page(
            path="Sidebar",
            content="# Sidebar",
            last_edited_by=request.user
        )
        sidebar.save()

    # Get the page.
    try:
        if specific_id:
            page = models.Page.objects.get(path=path, id=specific_id, is_deleted=False)
        else:
            page = models.Page.objects.filter(path=path, is_deleted=False).order_by("-last_updated")[0]

    # If there is no page, then we will send them to the PageForm.
    except (models.Page.DoesNotExist, IndexError):
        return redirect(reverse("edit", kwargs={'path': path}))

    return render(request, "wiki/page.html", {
        'sidebar': sidebar,
        'page': page,
    })

@login_required
def edit(request, path):
    """
    This is the edit page.
    """

    # Get all revisions.
    history = models.Page.objects.filter(path=path)

    # Get the page.
    try:
        page = models.Page.objects.filter(path=path, is_deleted=False).order_by("-last_updated")[0]
    # If there is no page, then create a stub.
    except (models.Page.DoesNotExist, IndexError):
        page = models.Page(
            path=path,
            content="This page is empty.",
            last_edited_by=request.user
        )

    if request.method == "POST":
        form = forms.PageForm(request.POST, instance=page)
        if form.is_valid():
            # Create a new page.
            new_page = models.Page(
                path=path,
                content=form.cleaned_data["content"],
                last_edited_by=request.user,
                is_deprecated=form.cleaned_data["is_deprecated"],
            )
            new_page.save()
            return redirect(reverse("page", kwargs={'path': path}))
    else:
        form = forms.PageForm(instance=page)

    return render(request, "wiki/edit.html", {
        'user': request.user,
        'page': page,
        'history': history,
        'form': form,
    })

@login_required
def search(request):

    if not "q" in request.GET:
        return HttpResponseForbidden()

    query = request.GET['q']

    results = documents.PageDocument.search().filter("term", content=query)

    return render(request, "wiki/search.html", {
        'query': query,
        'results': results,
    })


@login_required
def history(request):
    """
    This shows the history across all pages.
    """

    objects = models.Page.objects.all().order_by("-last_updated")
    paginator = Paginator(objects, 15)

    page_number = request.GET.get('page') or 1
    items = paginator.get_page(page_number)

    return render(request, 'wiki/history.html', {
        'items': items
    })
