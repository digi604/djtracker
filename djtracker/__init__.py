import datetime

from djtracker import models, utils

from django.contrib.auth.models import User
from django.contrib.comments.models import Comment
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.contrib.sites.models import Site
from django.conf import settings
from django.template import Context

def create_profile(sender, instance, created, **kwargs):    
    if created:
        profile = models.UserProfile()
        profile.user = instance
        profile.save()

def on_postsave_issue(sender, instance, created, **kwargs):
    if not hasattr(instance, '_dont_notify_watchers'):
        update_watchers(issue=instance, created=created)

def on_postsave_comment(sender, instance, created, **kwargs):
    update_watchers(issue=instance.content_object, comment=instance, created=created)

def update_watchers(issue, created, comment=None):    
    site = Site.objects.get(id=settings.SITE_ID)
    context = Context({'issue': issue, 'project': issue.project, 'site': site})
    
    if comment:
        # issue commented
        context['comment'] = comment
        context['user_name'] = comment.user_name
        template = utils.MailTemplate('djtracker/mail/issue_commented.mail')
    elif created:
        template = utils.MailTemplate('djtracker/mail/issue_created.mail')        
    else:
        template = utils.MailTemplate('djtracker/mail/issue_updated.mail')
        
    # we send email to: all watchers, the creator and the current processor...
    email_addresses = list(issue.watched_by.all().values_list('user__email', flat=True))
    for addy in issue.project.watched_by.all().values_list('user__email', flat=True):
        if addy not in email_addresses:
            email_addresses.append(addy)
    if issue.created_by:
        email_addresses.append(issue.created_by.user.email)
    if issue.assigned_to: 
        email_addresses.append(issue.assigned_to.user.email)
    # make list unique
    email_addresses = {}.fromkeys(email_addresses).keys()
    
    # send mails seperately to protect privacy
    for recipient in email_addresses:
        msg = template.render_to_mail(context)
        msg.from_address = settings.ISSUE_ADDRESS
        msg.to = [recipient,]
        msg.send()

def update_modified_time(sender, instance, created, **kwargs):
    comment = instance
    if comment.content_type.name == "issue":
        issue = comment.content_object
        issue.modified_date = datetime.datetime.now()
        # hack to prevent additional mail when new comment is added
        issue._dont_notify_watchers = True
        issue.save()

post_save.connect(create_profile, sender=User)
post_save.connect(on_postsave_comment, sender=Comment)
post_save.connect(on_postsave_issue, sender=models.Issue)
post_save.connect(update_modified_time, sender=Comment)

if not hasattr(settings, "WEB_SERVER"):
    settings.WEB_SERVER = 'apache'
