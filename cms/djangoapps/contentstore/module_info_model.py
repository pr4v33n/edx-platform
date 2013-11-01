from static_replace import replace_static_urls
from xmodule.modulestore.exceptions import ItemNotFoundError
from xblock.fields import Scope
from util.json_request import JsonResponse
from xmodule.modulestore.django import loc_mapper
from contentstore.utils import get_modulestore


def get_module_info(usage_loc, rewrite_static_links=False):
    """
    Old metadata, data, id representation of a leaf module fetcher.
    :param usage_loc: A BlockUsageLocator
    """
    old_location = loc_mapper().translate_locator_to_location(usage_loc)
    store = get_modulestore(old_location)
    try:
        module = store.get_item(old_location)
    except ItemNotFoundError:
        # create a new one
        store.create_and_save_xmodule(old_location)
        module = store.get_item(old_location)

    data = module.data
    if rewrite_static_links:
        # we pass a partially bogus course_id as we don't have the RUN information passed yet
        # through the CMS. Also the contentstore is also not RUN-aware at this point in time.
        data = replace_static_urls(
            module.data,
            None,
            course_id=module.location.org + '/' + module.location.course + '/BOGUS_RUN_REPLACE_WHEN_AVAILABLE'
        )

    return {
        'id': unicode(usage_loc),
        'data': data,
        'metadata': module.get_explicitly_set_fields_by_scope(Scope.settings)
    }


def set_module_info(usage_loc, post_data):
    """
    Old metadata, data, id representation leaf module updater.
    :param usage_loc: a BlockUsageLocator
    :param post_data: the payload with data, metadata, and possibly children (even tho the getter
    doesn't support children)
    """
    old_location = loc_mapper().translate_locator_to_location(usage_loc)
    store = get_modulestore(old_location)
    module = None
    try:
        module = store.get_item(old_location)
    except ItemNotFoundError:
        # new module at this location: almost always used for the course about pages; thus, no parent. (there
        # are quite a handful of about page types available for a course and only the overview is pre-created)
        store.create_and_save_xmodule(old_location)
        module = store.get_item(old_location)

    if post_data.get('data') is not None:
        data = post_data['data']
        store.update_item(old_location, data)
    else:
        data = module.get_explicitly_set_fields_by_scope(Scope.content)

    # cdodge: note calling request.POST.get('children') will return None if children is an empty array
    # so it lead to a bug whereby the last component to be deleted in the UI was not actually
    # deleting the children object from the children collection
    if 'children' in post_data and post_data['children'] is not None:
        children = post_data['children']
        store.update_children(old_location, children)

    # cdodge: also commit any metadata which might have been passed along in the
    # POST from the client, if it is there
    # NOTE, that the postback is not the complete metadata, as there's system metadata which is
    # not presented to the end-user for editing. So let's fetch the original and
    # 'apply' the submitted metadata, so we don't end up deleting system metadata
    if post_data.get('metadata') is not None:
        posted_metadata = post_data['metadata']

        # update existing metadata with submitted metadata (which can be partial)
        # IMPORTANT NOTE: if the client passed pack 'null' (None) for a piece of metadata that means 'remove it'
        for metadata_key, value in posted_metadata.items():
            field = module.fields[metadata_key]

            if value is None:
                # remove both from passed in collection as well as the collection read in from the modulestore
                field.delete_from(module)
            else:
                try:
                    value = field.from_json(value)
                except ValueError:
                    return JsonResponse({"error": "Invalid data"}, 400)
                field.write_to(module, value)

        # commit to datastore
        metadata = module.get_explicitly_set_fields_by_scope(Scope.settings)
        store.update_metadata(old_location, metadata)
    else:
        metadata = module.get_explicitly_set_fields_by_scope(Scope.settings)

    return {
        'id': unicode(usage_loc),
        'data': data,
        'metadata': metadata
    }
