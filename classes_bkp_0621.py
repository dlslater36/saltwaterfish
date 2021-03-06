from models import *
from django.db import connection
import collections

import time
import calendar


def GetCreditCardList(contactid):
  cards_list = []
  orders = Orders.objects.all().filter(ocustomerid = contactid)
  cards_hash = {}
  for order in orders:
    if order.ocardno:
      if order.ocardno not in cards_hash:
        cards_hash[order.ocardno] = "Card Ending in %s" %order.ocardno[-4:]

  # Preparing Cards List
  cards_list = []
  for key, value in cards_hash.items():
    cards_list.append((key, value))
  return cards_list  

def GenerateShippingCalander():
  month = [['', '', '','','', '', ''],
     ['', '', '','','', '', ''],
     ['', '', '','','', '', ''],
    ['', '', '','','', '', ''],
     ['', '', '','','', '', ''],
     ['', '', '','','', '', ''],
     ]

  today = time.localtime().tm_mday
  start_time = time.strptime("2013/06/01", "%Y/%m/01")
  day = start_time.tm_mday
  wday = start_time.tm_wday
  last_day = calendar.monthrange(start_time.tm_year, start_time.tm_mon)[1]

  row_no = 0
  while day <= last_day:
    cur_time = time.strptime(time.strftime("%Y/%m/" + str(day), start_time), "%Y/%m/%d")
    day = cur_time.tm_mday
    wday = cur_time.tm_wday
    script = ''
    bgcolor = "#FFFFFF"
    if day < today:
      bgcolor = "#999999"
    elif day == today:
      bgcolor = "#CC9966"
    elif day == today + 1:
      bgcolor = "#99CC00"
      script = time.strftime("%m/" + str(day).zfill(2) + "/%Y", start_time)
    elif day == today + 2:
      bgcolor = "#663366"
      script = time.strftime("%m/" + str(day).zfill(2) + "/%Y", start_time)
    elif day > today + 2:
      bgcolor = "#00CCCC"
      script = time.strftime("%m/" + str(day).zfill(2) + "/%Y", start_time)        

    if day >= today:
      if wday == 6:
         bgcolor = "#DB9E9B"
         script = ''
      elif wday == 5:
         script = time.strftime("%m/" + str(day).zfill(2) + "/%Y", start_time)
         bgcolor = "#FFCC33"


    day_hash = {'wday': wday, 'day': day, 'bgcolor':bgcolor, 'script':script}
    month[row_no][wday] = day_hash 
    if wday == 6:
      row_no += 1
    day += 1
  return month    


def GetPriorityShippingCharge(category_id):
  shipping_cat_obj = ShippingCategory.objects.filter(id = category_id, status='ACTIVE')[0]
  return shipping_cat_obj.priority_shipping 

def GetSaturdayShippingCharge(category_id):
  shipping_cat_obj = ShippingCategory.objects.filter(id = category_id, status='ACTIVE')[0]
  return shipping_cat_obj.saturday_delivery 

def GetAlaskaShippingCharge(category_id):
  shipping_cat_obj = ShippingCategory.objects.filter(id = category_id, status='ACTIVE')[0]
  return shipping_cat_obj.alaska_delivery 


class Error(object):
  def __init__(self):
    self.IsError = False
    self._error_number = 0
    self._error_message = ''
    
  def RaiseError(self, p_message):
    self.IsError = True
    self._error_message = p_message
    
  def Error(self):
    self.IsError = False;
    msg = self._error_message
    self._error_message = ""
    return msg 
  
class StoreCredit(object):
    def __init__(self):
      self.id = 0
      self.credit_value = 0.0

class MyShippingCategory(object):
  
  def __init__(self):
    self.id = -1
    self.shipping_charge = 0.0
    self.fuel_charge = 0.0
    self.tax = 0.0
    self.tax_value = 0.0
    self.promotions = 0.0
    self.shipping_value = 0.0
    self.supplies_total = 0.0
    self.freeshipping_diff = 0.0
    self.shipping_items = []

class CartInfo(Error):
  '''Holds final order summary of the Cart'''

  def __init__(self):
    super(CartInfo, self).__init__()
    self.subtotal = 0.0
    self.shipping_total = 0.0
    self.fuelcharge_total = 0.0
    self.tax_total = 0.0
    self.promotions_total = 0
    self.store_credit = 0.0
    self.order_total = 0.0

    self.is_storecredit_applied = False
    self.store_credit_id = 0
    self.store_credit = 0.0
    
    self.cc_approval_code = ''
    

  def ApplyStoreCredit(self, obj):
    self.store_credit_id = obj.id
    credit_value = obj.credit_value
    self.store_credit = credit_value
    if self.order_total >= self.store_credit:
      self.order_total -= self.store_credit
      self.store_credit = 0 
    elif self.order_total < self.store_credit and self.order_total > 0:
      self.store_credit -=  self.order_total
      self.order_total = 0

  
  def GetShippingCategoryID(self, catalog_id):
    #pc_object = ProductCategory.objects.get(catalogid=catalog_id)  
    #psc_object = ProductShippingCategories.objects.get(product_category_id = pc_object.categoryid)
    cursor = connection.cursor()
    cursor.execute("SELECT psc.shipping_category_id, sc.category_name FROM product_shipping_categories psc  "
                   "inner join product_category pc on (psc.product_category_id = pc.categoryid)  "
                   "inner join shipping_category sc on (psc.shipping_category_id = sc.id)"
                   "where product_category_id in (SELECT categoryid FROM product_category WHERE catalogid = %d) " %catalog_id)

    row = cursor.fetchone()
    cursor.close()
 
    shipping_category_id = row[0]
    shipping_category_name =  row[1]

    return shipping_category_id, shipping_category_name
  
  
  def Add(self, cart_dict, catalog_id):
    items_dict = cart_dict # key is ItemID and value is CartItem object 
    if catalog_id in items_dict.keys():
      cart_item = items_dict[catalog_id]
      # Checking whether the one more item is allowed the the existing quantity. 
      if (cart_item.quantity + 1) > cart_item.qoh:
        self.RaiseError("Quantity out of order. You can not add more items.")
        return items_dict
      
      cart_item.quantity += 1
      items_dict[catalog_id] = cart_item
    else:
      cart_item = CartItem(catalog_id)
      if cart_item.qoh <= 0:
        self.RaiseError("Quantity is out of order")
        return cart_dict
      
      cart_item.shipping_category, cart_item.shipping_category_name = self.GetShippingCategoryID(catalog_id)
      cart_item.quantity = 1
      items_dict[catalog_id] = cart_item
    return items_dict
  
  def Delete(self, cart_dict, catalog_id):
    del cart_dict[catalog_id]
    return cart_dict
  
  def Update(self, cart_dict, catalog_id, quantity):
    cart_item = cart_dict[catalog_id]
    if quantity <= 0:  
      self.RaiseError("Quantity should be greater than 0 or remove from cart")
      return cart_dict
        
    if quantity <= cart_item.qoh:
      cart_item.quantity = quantity
    else:
      self.RaiseError("Quantity is out of order")
      return cart_dict
 
    return cart_dict
    
  def GetOrderValue(self, cart_dict):
    order_value = 0
    for key, value in cart_dict.items():
      value.CalculateTotals()
      order_value += value.subtotal

    return order_value  

  def GetShippingCharge(self, category_id, shipping_value, state, excluded_zip_codes):
    shipping_charge = -1
    fuel_charge = 0
    free_shipping_diff = 0
    
    shipping_cat_obj = ShippingCategory.objects.filter(id = category_id, status='ACTIVE')[0]
    fuel_charge = shipping_cat_obj.fuel_charge
     
    if shipping_cat_obj.is_free_shipping == 1:
      # Return 0 as shipping charge and also get fuel charge as Tuple
      shipping_charge = 0
      return (shipping_charge, fuel_charge, free_shipping_diff) 

    if shipping_cat_obj.flatrate_shipping_charge > 0.0:
      shipping_charge = shipping_cat_obj.flatrate_shipping_charge
      return (shipping_charge, fuel_charge, free_shipping_diff)

    # Fetching Rules.
    shipping_charge_objs = ShippingCharges.objects.filter(shipping_category_id = category_id, 
                                                         order_total_min__lte = shipping_value,
                                                         order_total_max__gte = shipping_value,
                                                         shipping_state = state)
    # Calculating shipping charge as per the rules.
    # If no rules, applying flat_rate shipping charge 
    if shipping_charge_objs:
      shp_charge_obj = shipping_charge_objs[0]
      shipping_charge = shp_charge_obj.shipping_charge
    else:
      shipping_charge = shp_charge_obj.flatrate_shipping_charge
        
    # Calculating free shipping suggestion.
    if shipping_charge > 0:
      shipping_charge_objs = ShippingCharges.objects.filter(shipping_category_id = category_id,
                                                            shipping_charge = 0,
                                                            shipping_state = state)
      if shipping_charge_objs:
        shp_charge_obj = shipping_charge_objs[0]
        free_shipping_diff = (shp_charge_obj.order_total_min - shipping_value)
      else:
        free_shipping_diff = 0
      
    
    return (shipping_charge, fuel_charge, free_shipping_diff)
 
 
  def GetItemsByShippingCategory(self, cart_dict):
    items_dict = cart_dict
    state = 'FL'
    excluded_zips = []
    
    tax_list = Tax.objects.filter(tax_country = 'US', tax_state = state)

    if tax_list:
      tax = tax_list[0].tax_value1
    else:
      tax = 7.0

    # Dictionary contains shipping category id as a key and a list of items as values.
    shipping_categories_dict = {}
    shipping_cat_names_hash = {}
    # Collecting Category wise Items 
    for key, item in items_dict.items():
      item.CalculateTotals()
      shipping_category_id = item.shipping_category
      if item.shipping_category in shipping_categories_dict:
        shipping_categories_dict[item.shipping_category].append(item)
      else:
        shipping_categories_dict[item.shipping_category] = [item]
        shipping_cat_names_hash[item.shipping_category] = item.shipping_category_name
 

    # Calculating Shipping Charge, Fuel Charge and Tax for each category
    my_shipping_obj_list = [] 
    for key, value in shipping_categories_dict.items():
      shipping_category = MyShippingCategory()
      shipping_category.id = key
      shipping_category.name = shipping_cat_names_hash[key]
      shipping_category.shipping_items = value
      # Calculating Shipping Value
      for item in shipping_category.shipping_items:
        shipping_category.shipping_value += float(item.subtotal)
      
   
      (shipping_category.shipping_charge, shipping_category.fuel_charge, 
       shipping_category.freeshipping_diff) =  self.GetShippingCharge(shipping_category.id, 
                                                           shipping_category.shipping_value, 
                                                           state, excluded_zips)
      
      shipping_category.tax = tax
      shipping_category.tax_value = (shipping_category.shipping_value * shipping_category.tax)/100
      
      shipping_category.supplies_total = (shipping_category.shipping_value + 
                                          shipping_category.shipping_charge +
                                          shipping_category.fuel_charge +
                                          shipping_category.tax_value -
                                          shipping_category.promotions)                                    
                                            
      
      self.subtotal += shipping_category.shipping_value
      self.shipping_total +=  shipping_category.shipping_charge
      self.fuelcharge_total += shipping_category.fuel_charge
      self.tax_total += shipping_category.tax_value
      self.promotions_total += shipping_category.promotions
      
      my_shipping_obj_list.append(shipping_category)
    

    self.order_total = self.subtotal + self.shipping_total + self.fuelcharge_total + self.tax_total - self.promotions_total
    
    # Applying Store Credit        
    #if self.is_storecredit_applied:
     
    #od = collections.OrderedDict(sorted(shipping_categories_dict.items()))
 
    return my_shipping_obj_list
  
  def GetNumberOfItems(self, p_dict):
    cart_dict = p_dict;
    item_count = 0
    for key, value in cart_dict.items():
       item_count += value

    return item_count
  
class CartItem(Error):

  def __init__(self, item_id=None):
    super(CartItem, self).__init__()
   
    self.catalog_id = -1
    self.item_name = ''
    self.price = 0.0
    self.saleprice = 0.0
    self.quantity = 0
    self.qoh = 0 # (Quantity on Hand)
    self.shipping_category = 0
    self.shipping_category_name = ''
    self.shipping_charge = 0
    self.tax_percent = 0.0
    self.tax_value = 0.0
    self.fuel_charge = 0.0
    self.promotions = 0.0
    self.is_reward_enabled = False
    self.reward_points = 0
    self.thumbnail = ''
    self.image1 = ''
    self.image2 = ''
    self.image3 = ''
    self.extra_fied_3 = ''

    self.subtotal = 0.0
    self.shipping_total = 0.0
    self.fuel_charge_total = 0.0
    self.promotions_total = 0.0
    self.tax_total = 0.0
    self.supplies_total = 0.0

    if item_id:
      self.FillItem(item_id)
      return

  def CalculateTotals(self):
    if self.saleprice > 0:
      self.subtotal = self.saleprice * self.quantity
    else:
      self.subtotal = self.price * self.quantity  

    self.shipping_total = 0.0 
    self.fuel_charge_total = 0.0
    self.promotions_total = 0.0
    self.tax_total = 0.0
    self.supplies_total = 0.0

  def FillItem(self, p_catalog_id):
    '''Fills the current class object with the data fetched from the DB.
    Returns: False if product not found.
    '''
    # Fetching product from the DB.
    product_list = Products.objects.filter(catalogid=p_catalog_id)
    if not product_list:
      self.RaiseError("Item not found")
      return False

    
    product = product_list[0]
    #product = Products()
    self.catalog_id = product.catalogid
    self.item_name = product.name
    self.price = product.price
    self.saleprice = product.saleprice
    self.qoh = product.stock # (Quantity on Hand)
    
    # No need to fill the values. Will be calculated for every category.
    self.shipping_category = 0
    self.shipping_charge = 0
    self.tax_percent = 0.0
    self.tax_value = 0.0
    self.fuel_charge = 0.0

    # Update this value when User is applied Coupon. 
    self.promotions = 0.0
    
    if product.reward_disable == 1:  
      self.is_reward_enabled = False
    else:
      self.is_reward_enabled = True
      
    self.reward_points = product.reward_points
    self.thumbnail = product.thumbnail
    self.image1 = product.image1
    self.image2 = product.image2
    self.image3 = product.image3
    self.extra_fied_3 = product.extra_field_3

    #self.subtotal = 0.0
    #self.shipping_total = 0.0
    #self.fuel_charge_total = 0.0
    #self.promotions_total = 0.0
    #self.tax_total = 0.0
    #self.supplies_total = 0.0
    

  def Set(self, p_catalog_id, p_item_name, p_price, p_saleprice, p_quantity, 
               p_qoh, p_shipping_category, p_shipping_charge, p_tax_percent, 
               p_fuel_charge, p_promotions, p_is_rewards_enabled, 
               p_reward_points, p_thumbnail, p_image1, p_image2, p_image3, 
               p_extra_field_3=""):

    self.catalog_id = p_catalog_id
    self.item_name = p_item_name
    self.price = p_price
    self.saleprice = p_saleprice
    self.quantity = p_quantity
    self.qoh = p_qoh # (Quantity on Hand)
    self.shipping_category = p_shipping_category
    self.shipping_charge = p_shipping_charge
    self.tax_percent = p_tax_percent
    self.fuel_charge = p_fuel_charge
    self.promotions = p_promotions
    self.is_reward_enabled = p_is_rewards_enabled
    self.reward_points = p_reward_points
    self.thumbnail = p_thumbnail
    self.image1 = p_image1
    self.image2 = p_image2
    self.image3 = p_image3
    self.extra_fied_3 = p_extra_fied_3


#
#      self.id = id
#      self.name = name
#      self.quantity = quantity
#      self.price = price
#      self.saleprice = saleprice
#      #self.fuelcharge = fuelcharge
#      self.fuelcharge = 2.99 * quantity
#      self.promotions = promotions
#      if saleprice <= 0 :
#          self.subtotal = price * quantity
#      else:
#          self.subtotal = saleprice * quantity
#      
#      self.shipping = shipping
#      self.tax = tax
#      self.taxvalue = float(self.subtotal) * float(tax)/float(100)
#      self.total = float(self.subtotal) + float(shipping) + self.taxvalue + self.fuelcharge - self.promotions
#      self.thumbnail = thumbnail
#      self.image1 = image1
#      self.image2 = image2
#      self.image3 = image3
#      self.extra_field_3 = extra_field_3
#      
#      if reward_disable == 0:
#        self.reward_points = reward_points
#      else:
#        self.reward_points = 0   
#           
#      product_category_list = ProductCategory.objects.filter(catalogid = id)
#
#      logging.info(product_category_list[0].id)
#      if product_category_list:
#        category_id, category_name, parent_id = self.GetParentCategory(product_category_list[0].categoryid)
#
#      (self.shipping, free_shipping_min_value) = self.GetShippingCharge(category_name, self.subtotal)
#      self.free_shipping_suggestion_val = free_shipping_min_value - self.subtotal
#
#
#      self.category_id = 0
  
#  def GetParentCategory(self, category_id):
#    #SELECT category_name, category_parent from category where id = 4
#    cursor = connection.cursor()
#    parent_id = 99999
#    levels = 0
#    while (parent_id > 0 and levels < 100):
#      cursor.execute("SELECT id, category_name, category_parent from category where id = %d" %category_id)
#      row = cursor.fetchone()
#      category_id = row[0]
#      category_name = row[1]
#      parent_id = row[2]
#      category_id = parent_id
#      levels += 1
#
#    return (category_id, category_name, parent_id)
#
#  def GetShippingCharge(self, category_name, sub_total):
#      shipping_charge = 0.0
#      free_shipping_min_value = -1
#      if category_name.__contains__('Marine Life'):
#        free_shipping_min_value = 199
#        if sub_total >= 00.01 and sub_total <= 98.99:
#          shipping_charge = 34.99
#        elif sub_total >= 99.00 and sub_total <= 198.99:
#          shipping_charge = 24.99
#        else:
#          shipping_charge = 0
#            
#      elif category_name.__contains__('Live Goods'):
#        free_shipping_min_value = 199          
#        if sub_total >= 00.01 and sub_total <= 98.99:
#          shipping_charge = 34.99
#        elif sub_total >= 99.00 and sub_total <= 198.99:
#          shipping_charge = 24.99
#        else:
#          shipping_charge = 0
#
#      elif category_name.__contains__('Live Rock & Sand'):
#        free_shipping_min_value = 0
#        if sub_total >= 00.01 and sub_total <= 98.99:
#          shipping_charge = 4.99
#        elif sub_total >= 99.00 and sub_total <= 198.99:
#          shipping_charge = 4.99
#        else:
#          shipping_charge = 4.99
#
#      elif category_name.__contains__('FastTrack Supplies'):
#        free_shipping_min_value = 0
#        if sub_total >= 00.01 and sub_total <= 98.99:
#          shipping_charge = 4.99
#        elif sub_total >= 99.00 and sub_total <= 198.99:
#          shipping_charge = 4.99
#        else:
#          shipping_charge = 4.99
#
#      elif category_name.__contains__('Aquarium Supplies On Sale'):
#        free_shipping_min_value = 0
#        if sub_total >= 00.01 and sub_total <= 98.99:
#          shipping_charge = 4.99
#        elif sub_total >= 99.00 and sub_total <= 198.99:
#          shipping_charge = 4.99
#        else:
#          shipping_charge = 4.99
#
#      return (shipping_charge, free_shipping_min_value)

