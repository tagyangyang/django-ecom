from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError
import os
import uuid


class ProductManager(models.Manager):
    def get_queryset(self):
        return super(ProductManager, self).get_queryset().filter(is_active=True)
    
    def get_available_products(self):
        """获取可用的产品"""
        return self.get_queryset().filter(in_stock=True, is_active=True)
    
    def get_by_category(self, category_slug):
        """按分类获取产品"""
        return self.get_queryset().filter(category__slug=category_slug)


def validate_image_size(image):
    """验证图片大小"""
    file_size = image.file.size
    limit_mb = 5
    if file_size > limit_mb * 1024 * 1024:
        raise ValidationError(f"图片大小不能超过 {limit_mb} MB")


def validate_image_format(image):
    """验证图片格式"""
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ext = os.path.splitext(image.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(f"不支持的图片格式。支持的格式: {', '.join(valid_extensions)}")


class Category(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True, help_text="分类描述")
    is_active = models.BooleanField(default=True, help_text="是否激活")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'name']),
        ]

    def get_absolute_url(self):
        return reverse('store:category_list', args=[self.slug])

    def __str__(self):
        return self.name

    def product_count(self):
        """获取该分类下的产品数量"""
        return self.product.filter(is_active=True).count()


class Product(models.Model):
    category = models.ForeignKey(
        Category, 
        related_name='product',
        on_delete=models.CASCADE,
        help_text="产品分类"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='product_creator',
        help_text="创建者"
    )
    title = models.CharField(
        max_length=255, 
        db_index=True,
        help_text="产品标题"
    )
    author = models.CharField(
        max_length=255, 
        default='admin',
        help_text="作者"
    )
    sku = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        blank=True,
        help_text="库存单位 (SKU)，自动生成"
    )
    description = models.TextField(
        blank=True, 
        help_text="产品描述"
    )
    image = models.ImageField(
        upload_to='products/%Y/%m/%d/',
        validators=[validate_image_size, validate_image_format],
        help_text="产品图片 (最大5MB，支持jpg, png, gif, webp)"
    )
    slug = models.SlugField(
        max_length=255, 
        unique=True, 
        db_index=True,
        help_text="URL友好标识"
    )
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="价格 (最多99999999.99)"
    )
    discount_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True, 
        blank=True,
        validators=[MinValueValidator(0.01)],
        help_text="折扣价格"
    )
    in_stock = models.BooleanField(default=True, help_text="是否有库存")
    is_active = models.BooleanField(default=True, help_text="是否激活")
    featured = models.BooleanField(default=False, help_text="是否推荐")
    view_count = models.PositiveIntegerField(default=0, help_text="浏览次数")
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    products = ProductManager()

    class Meta:
        verbose_name_plural = 'Products'
        ordering = ('-created',)
        indexes = [
            models.Index(fields=['created']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'in_stock']),
            models.Index(fields=['featured', '-created']),
            models.Index(fields=['price']),
            models.Index(fields=['view_count']),
        ]

    def get_absolute_url(self):
        return reverse('store:product_detail', args=[self.slug])

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """保存时自动生成slug和SKU"""
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
        
        # 自动生成SKU
        if not self.sku:
            # 生成基于分类和UUID的SKU
            category_prefix = self.category.name[:3].upper() if self.category else 'PRO'
            unique_id = str(uuid.uuid4())[:8].upper()
            self.sku = f"{category_prefix}-{unique_id}"
        
        super().save(*args, **kwargs)

    def is_on_sale(self):
        """检查是否有折扣"""
        return self.discount_price is not None and self.discount_price < self.price

    def get_discount_percentage(self):
        """计算折扣百分比"""
        if self.is_on_sale():
            discount = ((self.price - self.discount_price) / self.price) * 100
            return round(discount, 1)
        return 0

    def increment_view_count(self):
        """增加浏览次数"""
        self.view_count += 1
        self.save(update_fields=['view_count'])


class ProductTag(models.Model):
    """产品标签模型"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductReview(models.Model):
    """产品评价模型"""
    RATING_CHOICES = [
        (1, '1星'),
        (2, '2星'),
        (3, '3星'),
        (4, '4星'),
        (5, '5星'),
    ]

    product = models.ForeignKey(
        Product, 
        related_name='reviews',
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        User,
        related_name='product_reviews',
        on_delete=models.CASCADE
    )
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200)
    comment = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['product', 'user']
        indexes = [
            models.Index(fields=['product', 'is_approved']),
            models.Index(fields=['rating']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.product.title} - {self.user.username} - {self.rating}星"

    def get_rating_display(self):
        return dict(self.RATING_CHOICES)[self.rating]
