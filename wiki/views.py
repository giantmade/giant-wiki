from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from wiki.models import FileUpload

from . import documents, forms, models


@login_required
def page(request, path="index", specific_id=False):
    """
    This displays a given wiki page.
    """

    # Get the sidebar.
    try:
        sidebar = models.Page.objects.filter(path="Sidebar").order_by("-last_updated")[
            0
        ]
    except (models.Page.DoesNotExist, IndexError):
        sidebar = models.Page(
            path="Sidebar", content="# Sidebar", last_edited_by=request.user
        )
        sidebar.save()

    # Get the page.
    try:
        if specific_id:
            page = models.Page.objects.get(path=path, id=specific_id, is_deleted=False)
        else:
            page = models.Page.objects.filter(path=path, is_deleted=False).order_by(
                "-last_updated"
            )[0]

    # If there is no page, then we will send them to the PageForm.
    except (models.Page.DoesNotExist, IndexError):
        return redirect(reverse("edit", kwargs={"path": path}))

    return render(
        request,
        "wiki/page.html",
        {
            "sidebar": sidebar,
            "page": page,
        },
    )



@login_required
def edit(request, path):
    """
    This is the edit page.
    """

    # Get all revisions.
    history = models.Page.objects.filter(path=path)

    # Get the page.
    try:
        page = models.Page.objects.filter(path=path, is_deleted=False).order_by(
            "-last_updated"
        )[0]
    # If there is no page, then create a stub.
    except (models.Page.DoesNotExist, IndexError):
        page = models.Page(
            path=path, content="This page is empty.", last_edited_by=request.user
        )

    if request.method == "POST":
        form = forms.PageForm(request.POST, request.FILES, request=request, instance=page)
        if form.is_valid():
            form.save()
            return redirect(reverse("page", kwargs={'path': path}))
    else:
        form = forms.PageForm(instance=page)

    return render(
        request,
        "wiki/edit.html",
        {
            "user": request.user,
            "page": page,
            "history": history,
            "form": form,
        },
    )


@login_required
def upload(request, path):
    if request.method == "POST":
        form = forms.AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect(reverse("page", kwargs={"path": path}))
    else:
        form = forms.AttachmentForm()

    return redirect(reverse("page", kwargs={"path": path}))


def delete(request, path, id):
    item = models.Attachments.objects.get(id=id)
    item.attachment.delete()
    item.delete()
    return redirect(reverse("page", kwargs={"path": path}))



@require_http_methods(['DELETE'])
@login_required
def remove_file(request, file_id):
    file = FileUpload.objects.filter(pk=file_id).first()
    if file:
        file.delete()
        return HttpResponse(f"Successfully deleted file '{file}'")
    return JsonResponse({'success': False})



@login_required
def search(request):

    if not "q" in request.GET:
        return HttpResponseForbidden()

    query = request.GET["q"]

    results = documents.PageDocument.search().filter("term", content=query)

    return render(
        request,
        "wiki/search.html",
        {
            "query": query,
            "results": results,
        },
    )


@login_required
def history(request):
    """
    This shows the history across all pages.
    """

    objects = models.Page.objects.all().order_by("-last_updated")
    paginator = Paginator(objects, 15)

    page_number = request.GET.get("page") or 1
    items = paginator.get_page(page_number)

    return render(request, "wiki/history.html", {"items": items})
