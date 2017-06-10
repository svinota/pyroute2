/*
 * Generic netlink sample -- kernel module
 * Use `make` to compile and `insmod` to load the module
 *
 * Sergiy Lozovsky <sergiy.lozovsky@gmail.com>
 * Peter V. Saveliev <peter@svinota.eu>
 *
 * Requires kernel 4.10+
 */
#include <linux/module.h>       /* Needed by all modules */
#include <linux/kernel.h>       /* Needed for KERN_INFO */
#include <linux/init.h>         /* Needed for the macros */
#include <net/genetlink.h>

/* attributes (variables): the index in this enum is used as a reference for the type,
 *             userspace application has to indicate the corresponding type
 *             the policy is used for security considerations
 */
enum {
    EXMPL_NLA_UNSPEC,
    EXMPL_NLA_DATA,
    EXMPL_NLA_LEN,
    __EXMPL_NLA_MAX,
};
/* ... and the same for commands
 */
enum {
    EXMPL_CMD_UNSPEC,
    EXMPL_CMD_MSG,
};

/* attribute policy: defines which attribute has which type (e.g int, char * etc)
 * possible values defined in net/netlink.h
 */
static struct nla_policy exmpl_genl_policy[__EXMPL_NLA_MAX] = {
        [EXMPL_NLA_DATA] = { .type = NLA_NUL_STRING },
        [EXMPL_NLA_LEN] = { .type = NLA_U32 },
};

#define VERSION_NR 1
static struct genl_family exmpl_gnl_family;

static int get_length(struct sk_buff *request, struct genl_info *info)
{
    struct sk_buff *reply;
    char *buffer;
    void *msg_head;

    if (info == NULL)
        return -EINVAL;

    if (!info->attrs[EXMPL_NLA_DATA])
        return -EINVAL;

    /* get the data */
    buffer = nla_data(info->attrs[EXMPL_NLA_DATA]);

    /* send a message back*/
    /* allocate some memory, since the size is not yet known use NLMSG_GOODSIZE*/
    reply = genlmsg_new(NLMSG_GOODSIZE, GFP_KERNEL);
    if (reply == NULL)
        return -ENOMEM;

    /* start the message */
    msg_head = genlmsg_put_reply(reply, info, &exmpl_gnl_family, 0, info->genlhdr->cmd);
    if (msg_head == NULL) {
        return -ENOMEM;
    }

    /* add a EXMPL_LEN attribute -- report the data length */
    if (0 != nla_put_u32(reply, EXMPL_NLA_LEN, strlen(buffer)))
        return -EINVAL;

    /* finalize the message */
    genlmsg_end(reply, msg_head);

    /* send the message back */
    if (0 != genlmsg_reply(reply, info))
        return -EINVAL;

    return 0;
}

/* commands: mapping between commands and actual functions*/
static const struct genl_ops exmpl_gnl_ops_echo[] = {
    {
        .cmd = EXMPL_CMD_MSG,
        .policy = exmpl_genl_policy,
        .doit = get_length,
    },
};

/* family definition */
static struct genl_family exmpl_gnl_family __ro_after_init = {
        .name = "EXMPL_GENL",           //the name of this family, used by userspace application
        .version = VERSION_NR,          //version number
        .maxattr = __EXMPL_NLA_MAX - 1,
        .module = THIS_MODULE,
        .ops = exmpl_gnl_ops_echo,
        .n_ops = ARRAY_SIZE(exmpl_gnl_ops_echo),
};



static int __init exmpl_gnl_init(void)
{
        int rc;
        rc = genl_register_family(&exmpl_gnl_family);
        if (rc != 0) {
            printk(KERN_INFO "rkmod: genl_register_family failed %d\n", rc);
            return 1;
        }
        printk(KERN_INFO "Generic netlink example loaded, protocol version %d\n", VERSION_NR);
        return 0;
}

static void __exit exmpl_gnl_exit(void)
{
        int ret;
        /*unregister the family*/
        ret = genl_unregister_family(&exmpl_gnl_family);
        if(ret !=0){
                printk("unregister family %i\n",ret);
        }
}

module_init(exmpl_gnl_init);
module_exit(exmpl_gnl_exit);

MODULE_LICENSE("GPL");
