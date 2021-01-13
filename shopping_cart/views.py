from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from books.models import Book
from .models import Order, OrderItem, Payment
import stripe
import string
import random
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))


# Create your views here.
@login_required
def add_to_cart(request, book_slug):
    book = get_object_or_404(Book, slug=book_slug)
    order_item, created = OrderItem.objects.get_or_create(book=book)
    order, created = Order.objects.get_or_create(user=request.user, is_ordered=False)
    order.items.add(order_item)
    order.save()
    messages.info(request, "Item successfully added to your cart")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


@login_required
def remove_from_cart(request, book_slug):
    book = get_object_or_404(Book, slug=book_slug)
    order_item = get_object_or_404(OrderItem, book=book)
    order = get_object_or_404(Order, user=request.user, is_ordered=False)
    order.items.remove(order_item)
    order.save()
    messages.info(request, "Item successfully removed from your cart")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


@login_required
def order_view(request):
    order_qs = Order.objects.filter(user=request.user, is_ordered=False)
    if order_qs.exists():
        context = {
            'order': order_qs[0],
        }
        return render(request, "order_summary.html", context)
    return Http404


@login_required
def checkout(request):
    order_qs =  Order.objects.filter(Order, user=request.user, is_ordered=False)
    if order_qs.exists():
        order = order_qs[0]
    else:
        return Http404
    if request.method == "POST":

        try:
            # Use Stripe's library to make requests...
            pass

            
            # complete the order (ref code and set ordered to true)
            order.ref_code = create_ref_code()
            
            # create a stripe charge
            token = request.POST.get('StripeToken')
            # `source` is obtained with Stripe.js; see https://stripe.com/docs/payments/accept-a-payment-charges#web-create-token
            charge = stripe.Charge.create(
            amount= int(order.get_total() * 100), #cents
            currency="usd",
            source="token",
            description= f"Charge for {request.user.username}",
            )


            # create our payment object and link to the order
            payment = Payment()
            payment.order = order
            payment.stripe_charge_id = charge.id
            payment.total_amount = order.get_total()
            payment.save()
        
            # add the book to the user's book list
            books = [item.book for item in order.items.all()]
            for book in books:
                request.user.userlibrary.books.add(book)

            order.is_ordered = True
            order.save()

            # redirect to the user's profile
            messages.success(request, "Your order was successful")
            return redirect("/account/profile")
            
            #send email to yourself

        except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
            messages.error(request, "There was a card error")
            return redirect(reverse("cart:checkout"))
        except stripe.error.RateLimitError as e:
        # Too many requests made to the API too quickly
            messages.error(request, "There was a rate limit error on Stripe")
            return redirect(reverse("cart:checkout"))
        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            messages.error(request, "Invalid parameters on Stripe request")
            return redirect(reverse("cart:checkout"))
        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            messages.error(request, "Invalid parameters on Stripe API Keys")
            return redirect(reverse("cart:checkout"))
        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            messages.error(request, "There was a network error, please try again")
            return redirect(reverse("cart:checkout"))
        except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
            messages.error(request, "There was a error, please try again")
            return redirect(reverse("cart:checkout"))
        except Exception as e:
            # Something else happened, completely unrelated to Stripe
            messages.error(request, "There was a serious error, we are working to resolve the issue")
            return redirect(reverse("cart:checkout"))

    context = {
        'order': order
    }

    return render(request, "checkout.html", context)