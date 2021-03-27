/**
 * @author: Dustin Utecht
 * @github: https://github.com/UtechtDustin
 */

const Utils = $.fn.bootstrapTable.utils

$.extend($.fn.bootstrapTable.defaults, {
    customView: false,
    showCustomView: false,
    showCustomViewButton: false
})

$.extend($.fn.bootstrapTable.defaults.icons, {
    customView: {
        bootstrap3: 'glyphicon glyphicon-eye-open',
        bootstrap4: 'fa fa-eye',
        semantic: 'fa fa-eye',
        foundation: 'fa fa-eye',
        bulma: 'fa fa-eye',
        materialize: 'remove_red_eye'
    }[$.fn.bootstrapTable.theme] || 'fa-eye'
})

$.extend($.fn.bootstrapTable.defaults, {
    onCustomViewPostBody() {
        return false
    },
    onCustomViewPreBody() {
        return false
    }
})

$.extend($.fn.bootstrapTable.locales, {
    formatToggleCustomView() {
        return 'Toggle custom view'
    }
})
$.extend($.fn.bootstrapTable.defaults, $.fn.bootstrapTable.locales)

$.fn.bootstrapTable.methods.push('toggleCustomView')

$.extend($.fn.bootstrapTable.Constructor.EVENTS, {
    'custom-view-post-body.bs.table': 'onCustomViewPostBody',
    'custom-view-pre-body.bs.table': 'onCustomViewPreBody'
})

$.BootstrapTable = class extends $.BootstrapTable {

    init() {
        this.showCustomView = this.options.showCustomView

        super.init()
    }

    initToolbar(...args) {
        super.initToolbar(...args)

        if (this.options.customView && this.options.showCustomViewButton) {
            const $btnGroup = this.$toolbar.find('>.' + this.constants.classes.buttonsGroup.split(' ').join('.')).first()
            let $btnToggleCustomView = $btnGroup.find('.toggle-custom-view')

            if (!$btnToggleCustomView.length) {
                $btnToggleCustomView = $(`
          <button class="toggle-custom-view ${this.constants.buttonsClass}"
          type="button" title="${this.options.formatToggleCustomView()}">
          ${this.options.showButtonIcons ? Utils.sprintf(this.constants.html.icon, this.options.iconsPrefix, this.options.icons.customView) : ''}
          ${this.options.showButtonText ? this.options.formatToggleCustomView() : ''}
          </button>
        `).appendTo($btnGroup)

                $btnToggleCustomView.on('click', $.proxy(this.toggleCustomView, this))
            }
        }
    }

    initBody() {
        super.initBody()

        if (!this.options.customView) {
            return
        }

        const $table = this.$el
        const $customViewContainer = this.$container.find('.fixed-table-custom-view')

        $table.hide()
        $customViewContainer.hide()
        if (!this.options.customView || !this.showCustomView) {
            $table.show()
            return
        }

        const data = this.getData().slice(this.pageFrom - 1, this.pageTo)
        const value = Utils.calculateObjectValue(this, this.options.customView, [data], '')
        this.trigger('custom-view-pre-body', data, value)
        if ($customViewContainer.length === 1) {
            $customViewContainer.show().html(value)
        } else {
            this.$tableBody.after(`<div class="fixed-table-custom-view">${value}</div>`)
        }

        this.trigger('custom-view-post-body', data, value)
    }

    toggleCustomView() {
        this.showCustomView = !this.showCustomView
        this.initBody()
    }
}
