from flask import Blueprint, jsonify, request, render_template, redirect, flash, url_for, current_app, abort


blogs = Blueprint('blogs', __name__)

# Define the available blog posts
BLOG_POSTS = {
    'effortless-international-shipping-from-belgium-with-ease': {
        'title': 'Effortless International Shipping from Belgium with Ease',
        'template': 'blogs/effortless-international-shipping-from-belgium-with-ease.html'
    },
    'cost-effective-shipping-from-cameroon-with-be-my-shipper': {
        'title': 'Cost-Effective Shipping from Cameroon with Be My Shipper',
        'template': 'blogs/cost-effective-shipping-from-cameroon-with-be-my-shipper.html'
    },
    'seamless-shipping-from-senegal-with-verified-travelers': {
        'title': 'Seamless Shipping from Senegal with Verified Travelers',
        'template': 'blogs/seamless-shipping-from-senegal-with-verified-travelers.html'
    },
    'affordable-shipping-from-guinea-conakry-with-travelers': {
        'title': 'Affordable Shipping from Guinea Conakry with Travelers',
        'template': 'blogs/affordable-shipping-from-guinea-conakry-with-travelers.html'
    },
    'international-shipping-from-ethiopia-guide-by-be-my-shipper': {
        'title': 'International Shipping from Ethiopia: Guide by Be My Shipper',
        'template': 'blogs/international-shipping-from-ethiopia-guide-by-be-my-shipper.html'
    },
    'international-shipping-from-the-uk-guide-by-be-my-shipper': {
        'title': 'International Shipping from the UK: Guide by Be My Shipper',
        'template': 'blogs/international-shipping-from-the-uk-guide-by-be-my-shipper.html'
    },
    'cheapest-shipping-services-in-2025-expert-tips-by-be-my-shipper': {
        'title': 'Cheapest Shipping Services in 2025: Expert Tips by Be My Shipper',
        'template': 'blogs/cheapest-shipping-services-in-2025-expert-tips-by-be-my-shipper.html'
    },
    'fast-and-cost-effective-shipping-from-senegal-be-my-shipper': {
        'title': 'Fast and Cost-Effective Shipping from Senegal | Be My Shipper',
        'template': 'blogs/fast-and-cost-effective-shipping-from-senegal-be-my-shipper.html'
    },
    'trusted-fast-and-affordable-shipping-from-america': {
        'title': 'Trusted, Fast, and Affordable Shipping From America - Be My Shipper',
        'template': 'blogs/trusted-fast-and-affordable-shipping-from-america.html'
    },
    'global-shipping-delivery-from-france-with-be-my-shipper': {
        'title': 'Global Shipping Delivery From France with Be My Shipper',
        'template': 'blogs/global-shipping-delivery-from-france-with-be-my-shipper.html'
    },
    'best-shipping-service-from-united-states-in-2025': {
        'title': 'Best Shipping Service From United States in 2025',
        'template': 'blogs/best-shipping-service-from-united-states-in-2025.html'
    }
}

@blogs.route('/blogs')
def blogs_home():
    return render_template('blogs.html')


@blogs.route('/blog/<slug>')
def blog_post(slug):
    # Check if the requested blog post exists
    if slug in BLOG_POSTS:
        return render_template(BLOG_POSTS[slug]['template'])
    else:
        # Return 404 if the blog post doesn't exist
        abort(404)


